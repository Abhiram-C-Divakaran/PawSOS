from sqlalchemy.types import TypeDecorator, Text
from geoalchemy2 import Geography

class PointField(TypeDecorator):
    """
    Cross-dialect spatial Point type:
    - On PostgreSQL: compiles to PostGIS Geography(geometry_type='POINT', srid=4326)
    - On SQLite (tests/dev): compiles to Text to allow running without SpatiaLite
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Geography(geometry_type="POINT", srid=4326))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            # If string 'POINT(lng lat)' or tuple (lat, lng), GeoAlchemy2 handles or format WKT
            if isinstance(value, (tuple, list)):
                return f"POINT({value[1]} {value[0]})"
            return value
        # For SQLite, serialize as WKT string
        if isinstance(value, (tuple, list)):
            return f"POINT({value[1]} {value[0]})"
        return str(value)

    def process_result_value(self, value, dialect):
        return value
