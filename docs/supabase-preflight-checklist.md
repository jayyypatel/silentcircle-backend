# Supabase Preflight Checklist

Run this in Supabase SQL editor before first migration:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

Verify extensions:

```sql
SELECT extname
FROM pg_extension
WHERE extname IN ('pgcrypto', 'pg_trgm')
ORDER BY extname;
```

Expected rows:
- `pgcrypto`
- `pg_trgm`
