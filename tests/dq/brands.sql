-- checks for brands: dupes, spaces, future dates. run with psql -f tests/dq/brands.sql
DO $$
DECLARE
    n BIGINT;
    c TEXT;
BEGIN
    -- duplicate pk rows
    EXECUTE '
        SELECT
            COUNT(*)
        FROM (
            SELECT
                "brand_id"
            FROM
                public.brands
            GROUP BY
                "brand_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'brands: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'brands dupes ok';

    -- leading/trailing/double spaces or empty strings in text cols
    FOREACH c IN ARRAY ARRAY['brand_name'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.brands
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
            RAISE EXCEPTION 'brands: %-space rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'brands spaces ok';

    -- no null pks or names
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.brands
        WHERE
            "brand_id" IS NULL
            OR "brand_name" IS NULL
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'brands: % null key/name rows', n;
    END IF;
    RAISE NOTICE 'brands nulls ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.brands
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'brands: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'brands dates ok';
END $$;
