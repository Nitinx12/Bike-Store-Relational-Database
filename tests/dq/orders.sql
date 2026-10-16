-- checks for orders: dupes, orphans, spaces, future dates. run with psql -f tests/dq/orders.sql
DO $$
DECLARE
    n BIGINT;
    c TEXT;
    i INT;
    child_cols TEXT[] := ARRAY[
        'customer_id',
        'store_id',
        'staff_id'
    ];
    ref_tbls TEXT[] := ARRAY[
        'customers',
        'stores',
        'staffs'
    ];
    ref_cols TEXT[] := ARRAY[
        'customer_id',
        'store_id',
        'staff_id'
    ];
BEGIN
    -- duplicate pk rows
    EXECUTE '
        SELECT
            COUNT(*)
        FROM (
            SELECT
                "order_id"
            FROM
                public.orders
            GROUP BY
                "order_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'orders: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'orders dupes ok';

    -- orphan fk rows
    FOR i IN 1 .. array_length(child_cols, 1) LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.orders AS c
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
            RAISE EXCEPTION 'orders: % orphan rows on % -> %.%',
                n, child_cols[i], ref_tbls[i], ref_cols[i];
        END IF;
    END LOOP;
    RAISE NOTICE 'orders orphans ok';

    -- leading/trailing/double spaces in status
    FOREACH c IN ARRAY ARRAY['order_status'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.orders
            WHERE
                %I IS NOT NULL
                AND (
                    %I <> btrim(%I)
                    OR strpos(%I, ''  '') > 0
                )',
            c, c, c, c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'orders: %-space rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'orders spaces ok';

    -- shipped before ordered makes no sense
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.orders
        WHERE
            "shipped_date" IS NOT NULL
            AND "order_date" IS NOT NULL
            AND "shipped_date" < "order_date"
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'orders: % rows shipped before ordered', n;
    END IF;
    RAISE NOTICE 'orders logic ok';

    -- status stays in the known set, required date never precedes order date
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.orders
        WHERE
            "order_status" NOT IN (
                ''Completed'',
                ''Pending'',
                ''Rejected'',
                ''Processing''
            )
            OR (
                "required_date" IS NOT NULL
                AND "order_date" IS NOT NULL
                AND "required_date" < "order_date"
            )
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'orders: % bad status/date rows', n;
    END IF;
    RAISE NOTICE 'orders domain ok';

    -- every order carries at least one item, else its total is zero
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.orders AS o
        WHERE
            NOT EXISTS (
                SELECT
                    1
                FROM
                    public.order_items AS i
                WHERE
                    i."order_id" = o."order_id"
            )
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'orders: % orders with no items', n;
    END IF;
    RAISE NOTICE 'orders maths ok';

    -- future dates (order dates live in the past, updated_at up to now)
    FOREACH c IN ARRAY ARRAY[
        'order_date',
        'required_date',
        'shipped_date'
    ] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.orders
            WHERE
                %I > CURRENT_DATE',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'orders: % future rows in %', n, c;
        END IF;
    END LOOP;
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.orders
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'orders: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'orders dates ok';
END $$;
