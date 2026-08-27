# Correction pass — frontend recovery slice-00

One pass. No extra review loop. No frontend code.

1. First code slice is shell + read-only inventory only. Fake Quick Create
   and Inbox are retired, not rebuilt.
2. Shop context in slice-01 comes from membership, not a required env
   shop ID. The env value may remain a local-only hint.
3. POS Find may share the read search; POS sell stays locked.
4. Notification UI on the old notification branch must not be copied;
   it still carries Convex.
5. Explicit sign-out is in slice-01 because canonical UI has none.
6. F0 exit does not unlock writes; locked nav must not look operational.
