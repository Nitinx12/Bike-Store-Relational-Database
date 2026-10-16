-- checks for products: dupes, orphans, spaces, future dates. run with psql -f tests/dq/products.sql
DO $$
DECLARE
    n BIGINT;
    c TEXT;
    i INT;
    child_cols TEXT[] := ARRAY[
        'brand_id',
        'category_id'
    ];
    ref_tbls TEXT[] := ARRAY[
        'brands',
        'categories'
    ];
    ref_cols TEXT[] := ARRAY[
        'brand_id',
        'category_id'
    ];
BEGIN
    -- duplicate pk rows
    EXECUTE '
        SELECT
            COUNT(*)
        FROM (
            SELECT
                "product_id"
            FROM
                public.products
            GROUP BY
                "product_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'products: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'products dupes ok';

    -- orphan fk rows
    FOR i IN 1 .. array_length(child_cols, 1) LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.products AS c
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
            RAISE EXCEPTION 'products: % orphan rows on % -> %.%',
                n, child_cols[i], ref_tbls[i], ref_cols[i];
        END IF;
    END LOOP;
    RAISE NOTICE 'products orphans ok';

    -- leading/trailing/double spaces or empty strings in text cols
    FOREACH c IN ARRAY ARRAY['product_name'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.products
            WHERE
                %I IS NOT NULL
                AND (
                    %I <> btrim(%I)
                    OR %I = ''''
                    OR strpos(%I, ''  '') > 0
                )',
            c, c, c, c, c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'products: %-space rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'products spaces ok';

    -- no null pks or names, catalog prices stay positive
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.products
        WHERE
            "product_id" IS NULL
            OR "product_name" IS NULL
            OR "list_price" IS NULL
            OR "list_price" <= 0
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'products: % bad key/name/price rows', n;
    END IF;
    RAISE NOTICE 'products nulls ok';

    -- model years stay within a sane range
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.products
        WHERE
            "model_year" IS NOT NULL
            AND (
                "model_year" < 2000
                OR "model_year" > EXTRACT(YEAR FROM CURRENT_DATE) + 1
            )
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'products: % bad model years', n;
    END IF;
    RAISE NOTICE 'products domain ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.products
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'products: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'products dates ok';
END $$;
