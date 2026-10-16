-- checks for order_items: dupes, orphans, bad numbers, future dates. run with psql -f tests/dq/order_items.sql
DO $$
DECLARE
    n BIGINT;
    c TEXT;
    i INT;
    child_cols TEXT[] := ARRAY[
        'order_id',
        'product_id'
    ];
    ref_tbls TEXT[] := ARRAY[
        'orders',
        'products'
    ];
    ref_cols TEXT[] := ARRAY[
        'order_id',
        'product_id'
    ];
BEGIN
    -- duplicate composite pk rows
    EXECUTE '
        SELECT
            COUNT(*)
        FROM (
            SELECT
                "order_id",
                "item_id"
            FROM
                public.order_items
            GROUP BY
                "order_id",
                "item_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'order_items: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'order_items dupes ok';

    -- orphan fk rows
    FOR i IN 1 .. array_length(child_cols, 1) LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.order_items AS c
            LEFT JOIN
                public.%I AS r
                ON r.%I = c.%I
            WHERE
                c.%I IS NOT NULL
                AND r.%I IS NULL',
            ref_tbls[i],
            ref_cols[i],
            child_cols[i],
            child_cols[i],
            ref_cols[i]
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'order_items: % orphan rows on % -> %.%',
                n, child_cols[i], ref_tbls[i], ref_cols[i];
        END IF;
    END LOOP;
    RAISE NOTICE 'order_items orphans ok';

    -- quantities and prices must not go negative, discount stays 0..1
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.order_items
        WHERE
            "quantity" <= 0
            OR "list_price" < 0
            OR "discount" < 0
            OR "discount" > 1
            OR "quantity" IS NULL
            OR "list_price" IS NULL
            OR "discount" IS NULL
            OR "total_value" IS NULL
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'order_items: % bad qty/price rows', n;
    END IF;
    RAISE NOTICE 'order_items numbers ok';

    -- line math holds: total = qty * price * (1 - discount), cent tolerance
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.order_items
        WHERE
            ABS(
                "total_value"
                - "quantity" * "list_price" * (1 - "discount")
            ) >= 0.01
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'order_items: % rows with wrong total_value', n;
    END IF;
    RAISE NOTICE 'order_items maths ok';

    -- item price matches the catalog price, cent tolerance
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.order_items AS i
        JOIN
            public.products AS p
            ON p."product_id" = i."product_id"
        WHERE
            ABS(i."list_price" - p."list_price") >= 0.01
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'order_items: % rows with off-catalog price', n;
    END IF;
    RAISE NOTICE 'order_items prices ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.order_items
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'order_items: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'order_items dates ok';
END $$;
