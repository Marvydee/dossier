"""A minimal in-memory stand-in for the Supabase client, covering just the
query shapes app/routers/*.py and app/worker.py actually use (select/insert
/update/delete with eq/in_ filters, and rpc calls). Not a general PostgREST
emulator — just enough to exercise route logic without a live database.
"""
import uuid


class _Result:
    def __init__(self, data):
        self.data = data


class _QueryBuilder:
    def __init__(self, store, table_name):
        self._store = store
        self._table = table_name
        self._mode = 'select'
        self._filters = []
        self._payload = None
        self._single = False

    def select(self, *_args, **_kwargs):
        self._mode = 'select'
        return self

    def insert(self, payload):
        self._mode = 'insert'
        self._payload = payload
        return self

    def update(self, payload):
        self._mode = 'update'
        self._payload = payload
        return self

    def delete(self):
        self._mode = 'delete'
        return self

    def eq(self, field, value):
        self._filters.append(('eq', field, value))
        return self

    def in_(self, field, values):
        self._filters.append(('in', field, list(values)))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def single(self):
        self._single = True
        return self

    def _matches(self, row):
        for op, field, value in self._filters:
            if op == 'eq' and row.get(field) != value:
                return False
            if op == 'in' and row.get(field) not in value:
                return False
        return True

    def execute(self):
        rows = self._store.setdefault(self._table, [])

        if self._mode == 'select':
            matched = [r for r in rows if self._matches(r)]
            return _Result(matched[0] if self._single and matched else
                            (None if self._single else matched))

        if self._mode == 'insert':
            payload = self._payload if isinstance(self._payload, list) else [self._payload]
            inserted = []
            for p in payload:
                row = dict(p)
                row.setdefault('id', str(uuid.uuid4()))
                rows.append(row)
                inserted.append(row)
            return _Result(inserted)

        if self._mode == 'update':
            updated = []
            for r in rows:
                if self._matches(r):
                    r.update(self._payload)
                    updated.append(r)
            return _Result(updated)

        if self._mode == 'delete':
            removed = [r for r in rows if self._matches(r)]
            rows[:] = [r for r in rows if not self._matches(r)]
            return _Result(removed)

        return _Result([])


class _RpcBuilder:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return _Result(self._data)


class _StorageBucket:
    def __init__(self, signed_url):
        self._signed_url = signed_url
        self.uploaded = []

    def upload(self, path, file_obj, options=None):
        self.uploaded.append(path)
        return {'path': path}

    def create_signed_url(self, path, expires_in):
        return {'signedURL': self._signed_url}


class FakeSupabaseClient:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.rpc_handlers = {}
        self.rpc_calls = []
        self._bucket = _StorageBucket('https://fake.supabase.co/signed/test.xlsx')

    def seed(self, table, rows):
        self.tables[table] = [dict(r) for r in rows]

    def table(self, name):
        return _QueryBuilder(self.tables, name)

    def on_rpc(self, name, handler):
        """handler(params: dict) -> data"""
        self.rpc_handlers[name] = handler

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        handler = self.rpc_handlers.get(name)
        data = handler(params) if handler else None
        return _RpcBuilder(data)

    @property
    def storage(self):
        return self

    def from_(self, _bucket_name):
        return self._bucket
