-- =============================================================================
-- customer_report.sql (PostgreSQL)
--
-- Dynamic, filterable customer report returned as a typed relational table.
-- Each row's "section" column identifies which columns are populated.
--
-- Sections : summary | frequency | cohort | top | bottom | recency | by_state
--            ('all' returns every section)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- Helper: builds the shared WHERE clause from the report filters
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION _cr_filter(
    p_start            date     DEFAULT NULL,
    p_end              date     DEFAULT NULL,
    p_states           text[]   DEFAULT NULL,
    p_cities           text[]   DEFAULT NULL,
    p_store_ids        bigint[] DEFAULT NULL,
    p_staff_ids        bigint[] DEFAULT NULL,
    p_brand_ids        bigint[] DEFAULT NULL,
    p_category_ids     bigint[] DEFAULT NULL,
    p_statuses         text[]   DEFAULT NULL,
    p_exclude_statuses text[]   DEFAULT NULL,
    p_search           text     DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    w text[] := ARRAY['TRUE'];
BEGIN
    IF p_start IS NOT NULL THEN
        w := w || format('o.order_date >= %L::date', p_start);
    END IF;

    IF p_end IS NOT NULL THEN
        w := w || format('o.order_date <= %L::date', p_end);
    END IF;

    IF p_states IS NOT NULL THEN
        w := w || format(
            'upper(c.state) = ANY (%L::text[])',
            (SELECT array_agg(upper(x)) FROM unnest(p_states) x)
        );
    END IF;

    IF p_cities IS NOT NULL THEN
        w := w || format(
            'lower(c.city) = ANY (%L::text[])',
            (SELECT array_agg(lower(x)) FROM unnest(p_cities) x)
        );
    END IF;

    IF p_store_ids IS NOT NULL THEN
        w := w || format('o.store_id = ANY (%L::bigint[])', p_store_ids);
    END IF;

    IF p_staff_ids IS NOT NULL THEN
        w := w || format('o.staff_id = ANY (%L::bigint[])', p_staff_ids);
    END IF;

    IF p_brand_ids IS NOT NULL THEN
        w := w || format('p.brand_id = ANY (%L::bigint[])', p_brand_ids);
    END IF;

    IF p_category_ids IS NOT NULL THEN
        w := w || format('p.category_id = ANY (%L::bigint[])', p_category_ids);
    END IF;

    IF p_statuses IS NOT NULL THEN
        w := w || format(
            'lower(o.order_status) = ANY (%L::text[])',
            (SELECT array_agg(lower(x)) FROM unnest(p_statuses) x)
        );
    END IF;

    IF p_exclude_statuses IS NOT NULL THEN
        w := w || format(
            'NOT (lower(o.order_status) = ANY (%L::text[]))',
            (SELECT array_agg(lower(x)) FROM unnest(p_exclude_statuses) x)
        );
    END IF;

    IF p_search IS NOT NULL AND p_search <> '' THEN
        w := w || format(
            '(c.first_name || '' '' || c.last_name || '' '' || coalesce(c.email,'''')) ILIKE %L',
            '%' || p_search || '%'
        );
    END IF;

    RETURN array_to_string(w, ' AND ');
END;
$$;


-- -----------------------------------------------------------------------------
-- The old output type must be removed before PostgreSQL can install TABLE output.
-- No CASCADE: existing dependencies should be reviewed rather than removed.
-- -----------------------------------------------------------------------------
DROP FUNCTION IF EXISTS customer_report(
    text[], date, date, text[], text[], bigint[], bigint[], bigint[], bigint[],
    text[], text[], text, int, numeric, int, text, date, int, int
);


-- -----------------------------------------------------------------------------
-- Main report function
-- -----------------------------------------------------------------------------
CREATE FUNCTION customer_report(
    p_sections         text[]   DEFAULT ARRAY['all'],
    p_start            date     DEFAULT NULL,
    p_end              date     DEFAULT NULL,
    p_states           text[]   DEFAULT NULL,
    p_cities           text[]   DEFAULT NULL,
    p_store_ids        bigint[] DEFAULT NULL,
    p_staff_ids        bigint[] DEFAULT NULL,
    p_brand_ids        bigint[] DEFAULT NULL,
    p_category_ids     bigint[] DEFAULT NULL,
    p_statuses         text[]   DEFAULT NULL,
    p_exclude_statuses text[]   DEFAULT NULL,
    p_search           text     DEFAULT NULL,
    p_min_orders       int      DEFAULT 1,
    p_min_revenue      numeric  DEFAULT 0,
    p_top_n            int      DEFAULT 10,
    p_sort_by          text     DEFAULT 'revenue',
    p_as_of            date     DEFAULT NULL,
    p_active_days      int      DEFAULT 90,
    p_lapsed_days      int      DEFAULT 180
)
RETURNS TABLE (
    section                    text,
    customers                  bigint,
    orders                     bigint,
    revenue                    numeric,
    avg_order_value            numeric,
    avg_orders_per_customer    numeric,
    repeat_customers           bigint,
    repeat_rate_pct            numeric,
    repeat_revenue_share_pct   numeric,
    avg_days_between_orders    numeric,
    top10pct_revenue_share     numeric,
    as_of                      date,
    orders_bucket              text,
    pct_of_customers           numeric,
    cohort                     date,
    cohort_size                bigint,
    month_offset               int,
    active_customers           bigint,
    retention_pct              numeric,
    customer_id                bigint,
    name                       text,
    email                      text,
    city                       text,
    state                      text,
    items                      bigint,
    aov                        numeric,
    first_order                date,
    last_order                 date,
    days_since_last            int,
    segment                    text
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_filter text;
    v_cte    text;
    v_sql    text;
BEGIN
    -- -------------------------------------------------------------------------
    -- Parameter validation
    -- -------------------------------------------------------------------------
    IF p_sort_by NOT IN ('revenue', 'orders', 'items', 'aov', 'first_order', 'last_order') THEN
        RAISE EXCEPTION
            'p_sort_by must be one of revenue, orders, items, aov, first_order, last_order (got %)',
            p_sort_by;
    END IF;

    IF p_top_n IS NULL OR p_top_n < 1 THEN
        p_top_n := 10;
    END IF;

    -- -------------------------------------------------------------------------
    -- Shared filter and CTE logic (retained from the original report)
    -- -------------------------------------------------------------------------
    v_filter := _cr_filter(
        p_start, p_end, p_states, p_cities, p_store_ids, p_staff_ids,
        p_brand_ids, p_category_ids, p_statuses, p_exclude_statuses, p_search
    );

    v_cte := format($q$
        WITH lines AS (
            SELECT  o.order_id,
                    o.order_date,
                    o.customer_id,
                    c.first_name || ' ' || c.last_name AS name,
                    c.email,
                    c.city,
                    c.state,
                    oi.quantity,
                    oi.total_value
            FROM    orders      o
            JOIN    customers   c  ON c.customer_id = o.customer_id
            JOIN    order_items oi ON oi.order_id   = o.order_id
            JOIN    products    p  ON p.product_id  = oi.product_id
            WHERE   %1$s
        ),

        asof AS (
            SELECT  COALESCE(%2$L::date, max(order_date)) AS d
            FROM    lines
        ),

        cust AS (
            SELECT  customer_id,
                    max(name)                                            AS name,
                    max(email)                                           AS email,
                    max(city)                                            AS city,
                    max(state)                                           AS state,
                    count(DISTINCT order_id)                             AS orders,
                    sum(quantity)                                        AS items,
                    sum(total_value)                                     AS revenue,
                    round(sum(total_value) / count(DISTINCT order_id), 2) AS aov,
                    min(order_date)                                      AS first_order,
                    max(order_date)                                      AS last_order
            FROM    lines
            GROUP BY customer_id
            HAVING  count(DISTINCT order_id) >= %3$L::int
               AND  sum(total_value)         >= %4$L::numeric
        ),

        ord AS (
            SELECT  l.customer_id,
                    l.order_id,
                    min(l.order_date) AS order_date
            FROM    lines l
            JOIN    cust  USING (customer_id)
            GROUP BY l.customer_id, l.order_id
        ),

        gaps AS (
            SELECT  customer_id,
                    order_date
                        - lag(order_date) OVER (
                              PARTITION BY customer_id
                              ORDER BY order_date, order_id
                          ) AS gap
            FROM    ord
        ),

        coh AS (
            SELECT  customer_id,
                    date_trunc('month', first_order)::date AS cohort
            FROM    cust
        ),

        csize AS (
            SELECT  cohort,
                    count(*) AS sz
            FROM    coh
            GROUP BY cohort
        ),

        act AS (
            SELECT  coh.cohort,
                    (
                        (extract(year  FROM o.order_date) * 12 + extract(month FROM o.order_date))
                      - (extract(year  FROM coh.cohort)   * 12 + extract(month FROM coh.cohort))
                    )::int AS m,
                    count(DISTINCT o.customer_id) AS n
            FROM    ord o
            JOIN    coh USING (customer_id)
            GROUP BY 1, 2
        )
    $q$, v_filter, p_as_of, p_min_orders, p_min_revenue);


    -- =========================================================================
    -- Section: summary
    -- =========================================================================
    IF p_sections && ARRAY['all', 'summary'] THEN
        RETURN QUERY EXECUTE v_cte || $s$
            SELECT  'summary'::text,                                                    -- section
                    count(*)::bigint,                                                   -- customers
                    sum(orders)::bigint,                                                -- orders
                    sum(revenue)::numeric,                                              -- revenue
                    round(sum(revenue) / NULLIF(sum(orders), 0), 2)::numeric,           -- avg_order_value
                    round(avg(orders), 2)::numeric,                                     -- avg_orders_per_customer
                    count(*) FILTER (WHERE orders > 1)::bigint,                         -- repeat_customers
                    round(100.0 * count(*) FILTER (WHERE orders > 1)
                                / NULLIF(count(*), 0), 2)::numeric,                     -- repeat_rate_pct
                    round(100.0 * sum(revenue) FILTER (WHERE orders > 1)
                                / NULLIF(sum(revenue), 0), 2)::numeric,                 -- repeat_revenue_share_pct
                    (SELECT round(avg(gap), 1)::numeric FROM gaps),                     -- avg_days_between_orders
                    (
                        SELECT  round(100.0 * sum(revenue) FILTER (WHERE rn <= ceil(0.1 * cnt))
                                    / NULLIF(sum(revenue), 0), 2)::numeric
                        FROM    (
                                    SELECT  revenue,
                                            row_number() OVER (ORDER BY revenue DESC) AS rn,
                                            count(*)     OVER ()                      AS cnt
                                    FROM    cust
                                ) x
                    ),                                                                  -- top10pct_revenue_share
                    (SELECT d FROM asof),                                               -- as_of
                    NULL::text,                                                         -- orders_bucket
                    NULL::numeric,                                                      -- pct_of_customers
                    NULL::date,                                                         -- cohort
                    NULL::bigint,                                                       -- cohort_size
                    NULL::int,                                                          -- month_offset
                    NULL::bigint,                                                       -- active_customers
                    NULL::numeric,                                                      -- retention_pct
                    NULL::bigint,                                                       -- customer_id
                    NULL::text,                                                         -- name
                    NULL::text,                                                         -- email
                    NULL::text,                                                         -- city
                    NULL::text,                                                         -- state
                    NULL::bigint,                                                       -- items
                    NULL::numeric,                                                      -- aov
                    NULL::date,                                                         -- first_order
                    NULL::date,                                                         -- last_order
                    NULL::int,                                                          -- days_since_last
                    NULL::text                                                          -- segment
            FROM    cust
        $s$;
    END IF;


    -- =========================================================================
    -- Section: frequency (customers bucketed by number of orders)
    -- =========================================================================
    IF p_sections && ARRAY['all', 'frequency'] THEN
        RETURN QUERY EXECUTE v_cte || $s$
            SELECT  'frequency'::text,                                                  -- section
                    n::bigint,                                                          -- customers
                    NULL::bigint,                                                       -- orders
                    r::numeric,                                                         -- revenue
                    NULL::numeric,                                                      -- avg_order_value
                    NULL::numeric,                                                      -- avg_orders_per_customer
                    NULL::bigint,                                                       -- repeat_customers
                    NULL::numeric,                                                      -- repeat_rate_pct
                    NULL::numeric,                                                      -- repeat_revenue_share_pct
                    NULL::numeric,                                                      -- avg_days_between_orders
                    NULL::numeric,                                                      -- top10pct_revenue_share
                    NULL::date,                                                         -- as_of
                    b::text,                                                            -- orders_bucket
                    round(100.0 * n / sum(n) OVER (), 2)::numeric,                      -- pct_of_customers
                    NULL::date,                                                         -- cohort
                    NULL::bigint,                                                       -- cohort_size
                    NULL::int,                                                          -- month_offset
                    NULL::bigint,                                                       -- active_customers
                    NULL::numeric,                                                      -- retention_pct
                    NULL::bigint,                                                       -- customer_id
                    NULL::text,                                                         -- name
                    NULL::text,                                                         -- email
                    NULL::text,                                                         -- city
                    NULL::text,                                                         -- state
                    NULL::bigint,                                                       -- items
                    NULL::numeric,                                                      -- aov
                    NULL::date,                                                         -- first_order
                    NULL::date,                                                         -- last_order
                    NULL::int,                                                          -- days_since_last
                    NULL::text                                                          -- segment
            FROM    (
                        SELECT  CASE WHEN orders >= 5 THEN '5+' ELSE orders::text END AS b,
                                min(least(orders, 5))                                 AS ord,
                                count(*)                                              AS n,
                                sum(revenue)                                          AS r
                        FROM    cust
                        GROUP BY 1
                    ) t
            ORDER BY ord
        $s$;
    END IF;


    -- =========================================================================
    -- Section: cohort (monthly retention by first-order month)
    -- =========================================================================
    IF p_sections && ARRAY['all', 'cohort'] THEN
        RETURN QUERY EXECUTE v_cte || $s$
            SELECT  'cohort'::text,                                                     -- section
                    NULL::bigint,                                                       -- customers
                    NULL::bigint,                                                       -- orders
                    NULL::numeric,                                                      -- revenue
                    NULL::numeric,                                                      -- avg_order_value
                    NULL::numeric,                                                      -- avg_orders_per_customer
                    NULL::bigint,                                                       -- repeat_customers
                    NULL::numeric,                                                      -- repeat_rate_pct
                    NULL::numeric,                                                      -- repeat_revenue_share_pct
                    NULL::numeric,                                                      -- avg_days_between_orders
                    NULL::numeric,                                                      -- top10pct_revenue_share
                    NULL::date,                                                         -- as_of
                    NULL::text,                                                         -- orders_bucket
                    NULL::numeric,                                                      -- pct_of_customers
                    s.cohort::date,                                                     -- cohort
                    s.sz::bigint,                                                       -- cohort_size
                    a.m::int,                                                           -- month_offset
                    a.n::bigint,                                                        -- active_customers
                    round(100.0 * a.n / s.sz, 1)::numeric,                              -- retention_pct
                    NULL::bigint,                                                       -- customer_id
                    NULL::text,                                                         -- name
                    NULL::text,                                                         -- email
                    NULL::text,                                                         -- city
                    NULL::text,                                                         -- state
                    NULL::bigint,                                                       -- items
                    NULL::numeric,                                                      -- aov
                    NULL::date,                                                         -- first_order
                    NULL::date,                                                         -- last_order
                    NULL::int,                                                          -- days_since_last
                    NULL::text                                                          -- segment
            FROM    csize s
            JOIN    act   a USING (cohort)
            ORDER BY s.cohort, a.m
        $s$;
    END IF;


    -- =========================================================================
    -- Section: top (best customers by p_sort_by)
    -- =========================================================================
    IF p_sections && ARRAY['all', 'top'] THEN
        v_sql := format($s$
            SELECT  'top'::text,                                                        -- section
                    NULL::bigint,                                                       -- customers
                    orders::bigint,                                                     -- orders
                    NULL::numeric,                                                      -- revenue
                    NULL::numeric,                                                      -- avg_order_value
                    NULL::numeric,                                                      -- avg_orders_per_customer
                    NULL::bigint,                                                       -- repeat_customers
                    NULL::numeric,                                                      -- repeat_rate_pct
                    NULL::numeric,                                                      -- repeat_revenue_share_pct
                    NULL::numeric,                                                      -- avg_days_between_orders
                    NULL::numeric,                                                      -- top10pct_revenue_share
                    NULL::date,                                                         -- as_of
                    NULL::text,                                                         -- orders_bucket
                    NULL::numeric,                                                      -- pct_of_customers
                    NULL::date,                                                         -- cohort
                    NULL::bigint,                                                       -- cohort_size
                    NULL::int,                                                          -- month_offset
                    NULL::bigint,                                                       -- active_customers
                    NULL::numeric,                                                      -- retention_pct
                    customer_id::bigint,                                                -- customer_id
                    name::text,                                                         -- name
                    email::text,                                                        -- email
                    city::text,                                                         -- city
                    state::text,                                                        -- state
                    items::bigint,                                                      -- items
                    aov::numeric,                                                       -- aov
                    first_order::date,                                                  -- first_order
                    last_order::date,                                                   -- last_order
                    ((SELECT d FROM asof) - last_order)::int,                           -- days_since_last
                    NULL::text                                                          -- segment
            FROM    cust
            ORDER BY %1$I DESC NULLS LAST, customer_id
            LIMIT   %2$s
        $s$, p_sort_by, p_top_n);

        RETURN QUERY EXECUTE v_cte || v_sql;
    END IF;


    -- =========================================================================
    -- Section: bottom (weakest customers by p_sort_by)
    -- =========================================================================
    IF p_sections && ARRAY['all', 'bottom'] THEN
        v_sql := format($s$
            SELECT  'bottom'::text,                                                     -- section
                    NULL::bigint,                                                       -- customers
                    orders::bigint,                                                     -- orders
                    NULL::numeric,                                                      -- revenue
                    NULL::numeric,                                                      -- avg_order_value
                    NULL::numeric,                                                      -- avg_orders_per_customer
                    NULL::bigint,                                                       -- repeat_customers
                    NULL::numeric,                                                      -- repeat_rate_pct
                    NULL::numeric,                                                      -- repeat_revenue_share_pct
                    NULL::numeric,                                                      -- avg_days_between_orders
                    NULL::numeric,                                                      -- top10pct_revenue_share
                    NULL::date,                                                         -- as_of
                    NULL::text,                                                         -- orders_bucket
                    NULL::numeric,                                                      -- pct_of_customers
                    NULL::date,                                                         -- cohort
                    NULL::bigint,                                                       -- cohort_size
                    NULL::int,                                                          -- month_offset
                    NULL::bigint,                                                       -- active_customers
                    NULL::numeric,                                                      -- retention_pct
                    customer_id::bigint,                                                -- customer_id
                    name::text,                                                         -- name
                    email::text,                                                        -- email
                    city::text,                                                         -- city
                    state::text,                                                        -- state
                    items::bigint,                                                      -- items
                    aov::numeric,                                                       -- aov
                    first_order::date,                                                  -- first_order
                    last_order::date,                                                   -- last_order
                    ((SELECT d FROM asof) - last_order)::int,                           -- days_since_last
                    NULL::text                                                          -- segment
            FROM    cust
            ORDER BY %1$I ASC NULLS LAST, customer_id
            LIMIT   %2$s
        $s$, p_sort_by, p_top_n);

        RETURN QUERY EXECUTE v_cte || v_sql;
    END IF;


    -- =========================================================================
    -- Section: recency (Active / At risk / Lapsed segments)
    -- =========================================================================
    IF p_sections && ARRAY['all', 'recency'] THEN
        v_sql := format($s$
            SELECT  'recency'::text,                                                    -- section
                    n::bigint,                                                          -- customers
                    NULL::bigint,                                                       -- orders
                    rev::numeric,                                                       -- revenue
                    NULL::numeric,                                                      -- avg_order_value
                    NULL::numeric,                                                      -- avg_orders_per_customer
                    rep::bigint,                                                        -- repeat_customers
                    NULL::numeric,                                                      -- repeat_rate_pct
                    NULL::numeric,                                                      -- repeat_revenue_share_pct
                    NULL::numeric,                                                      -- avg_days_between_orders
                    NULL::numeric,                                                      -- top10pct_revenue_share
                    NULL::date,                                                         -- as_of
                    NULL::text,                                                         -- orders_bucket
                    round(100.0 * n / sum(n) OVER (), 2)::numeric,                      -- pct_of_customers
                    NULL::date,                                                         -- cohort
                    NULL::bigint,                                                       -- cohort_size
                    NULL::int,                                                          -- month_offset
                    NULL::bigint,                                                       -- active_customers
                    NULL::numeric,                                                      -- retention_pct
                    NULL::bigint,                                                       -- customer_id
                    NULL::text,                                                         -- name
                    NULL::text,                                                         -- email
                    NULL::text,                                                         -- city
                    NULL::text,                                                         -- state
                    NULL::bigint,                                                       -- items
                    NULL::numeric,                                                      -- aov
                    NULL::date,                                                         -- first_order
                    NULL::date,                                                         -- last_order
                    NULL::int,                                                          -- days_since_last
                    seg::text                                                           -- segment
            FROM    (
                        SELECT  CASE
                                    WHEN dsl <= %1$L::int THEN 'Active'
                                    WHEN dsl <= %2$L::int THEN 'At risk'
                                    ELSE 'Lapsed'
                                END AS seg,
                                CASE
                                    WHEN dsl <= %1$L::int THEN 1
                                    WHEN dsl <= %2$L::int THEN 2
                                    ELSE 3
                                END AS ord,
                                count(*)                              AS n,
                                count(*) FILTER (WHERE orders > 1)    AS rep,
                                sum(revenue)                          AS rev
                        FROM    (
                                    SELECT  *,
                                            (SELECT d FROM asof) - last_order AS dsl
                                    FROM    cust
                                ) z
                        GROUP BY 1, 2
                    ) t
            ORDER BY ord
        $s$, p_active_days, p_lapsed_days);

        RETURN QUERY EXECUTE v_cte || v_sql;
    END IF;


    -- =========================================================================
    -- Section: by_state (top p_top_n states by revenue)
    -- =========================================================================
    IF p_sections && ARRAY['all', 'by_state'] THEN
        v_sql := format($s$
            SELECT  'by_state'::text,                                                   -- section
                    count(*)::bigint,                                                   -- customers
                    sum(orders)::bigint,                                                -- orders
                    sum(revenue)::numeric,                                              -- revenue
                    NULL::numeric,                                                      -- avg_order_value
                    NULL::numeric,                                                      -- avg_orders_per_customer
                    NULL::bigint,                                                       -- repeat_customers
                    round(100.0 * count(*) FILTER (WHERE orders > 1)
                                / count(*), 1)::numeric,                                -- repeat_rate_pct
                    NULL::numeric,                                                      -- repeat_revenue_share_pct
                    NULL::numeric,                                                      -- avg_days_between_orders
                    NULL::numeric,                                                      -- top10pct_revenue_share
                    NULL::date,                                                         -- as_of
                    NULL::text,                                                         -- orders_bucket
                    NULL::numeric,                                                      -- pct_of_customers
                    NULL::date,                                                         -- cohort
                    NULL::bigint,                                                       -- cohort_size
                    NULL::int,                                                          -- month_offset
                    NULL::bigint,                                                       -- active_customers
                    NULL::numeric,                                                      -- retention_pct
                    NULL::bigint,                                                       -- customer_id
                    NULL::text,                                                         -- name
                    NULL::text,                                                         -- email
                    NULL::text,                                                         -- city
                    state::text,                                                        -- state
                    NULL::bigint,                                                       -- items
                    NULL::numeric,                                                      -- aov
                    NULL::date,                                                         -- first_order
                    NULL::date,                                                         -- last_order
                    NULL::int,                                                          -- days_since_last
                    NULL::text                                                          -- segment
            FROM    cust
            GROUP BY state
            ORDER BY sum(revenue) DESC
            LIMIT   %1$s
        $s$, p_top_n);

        RETURN QUERY EXECUTE v_cte || v_sql;
    END IF;
END;
$$;


-- =============================================================================
-- Examples
-- =============================================================================
--   SELECT * FROM customer_report();
--
--   SELECT  customer_id, name, orders, items, aov,
--           first_order, last_order, days_since_last
--   FROM    customer_report(ARRAY['top'], p_top_n => 10)
--   WHERE   section = 'top';
--
--   SELECT  cohort, cohort_size, month_offset, active_customers, retention_pct
--   FROM    customer_report(ARRAY['cohort'])
--   WHERE   section = 'cohort';