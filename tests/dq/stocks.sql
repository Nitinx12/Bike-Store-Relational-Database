-- checks for stocks: dupes, orphans, bad qty, future dates. run with psql -f tests/dq/stocks.sql
DO $$
DECLARE
    n BIGINT;
    c TEXT;
    i INT;
    child_cols TEXT[] := ARRAY[
        'store_id',
        'product_id'
    ];
    ref_tbls TEXT[] := ARRAY[
        'stores',
        'products'
    ];
    ref_cols TEXT[] := ARRAY[
        'store_id',
        'product_id'
    ];
BEGIN
    -- duplicate composite pk rows
    EXECUTE '
        SELECT
            COUNT(*)
        FROM (
            SELECT
                "store_id",
                "product_id"
            FROM
                public.stocks
            GROUP BY
                "store_id",
                "product_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'stocks: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'stocks dupes ok';

    -- orphan fk rows
    FOR i IN 1 .. array_length(child_cols, 1) LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.stocks AS c
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
            RAISE EXCEPTION 'stocks: % orphan rows on % -> %.%',
                n, child_cols[i], ref_tbls[i], ref_cols[i];
        END IF;
    END LOOP;
    RAISE NOTICE 'stocks orphans ok';

    -- stock cannot go negative
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.stocks
        WHERE
            "quantity" < 0
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'stocks: % negative qty rows', n;
    END IF;
    RAISE NOTICE 'stocks numbers ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.stocks
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'stocks: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'stocks dates ok';
END $$;
