# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import logging
import re
from datetime import datetime
from re import Pattern
from typing import Any, Optional, TypedDict

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from flask_babel import gettext as __
from marshmallow import fields, Schema
from sqlalchemy import types
from sqlalchemy.dialects.mssql.base import SMALLDATETIME
from sqlalchemy.engine.url import URL

from superset.constants import TimeGrain
from superset.databases.utils import make_url_safe
from superset.db_engine_specs.base import (
    BaseEngineSpec,
    BasicPropertiesType,
    DatabaseCategory,
)
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.models.sql_types.mssql_sql_types import GUID
from superset.utils.core import GenericDataType

logger = logging.getLogger(__name__)


# Regular expressions to catch custom errors
CONNECTION_ACCESS_DENIED_REGEX = re.compile("Adaptive Server connection failed")
CONNECTION_INVALID_HOSTNAME_REGEX = re.compile(
    r"Adaptive Server is unavailable or does not exist \((?P<hostname>.*?)\)"
    "(?!.*Net-Lib error).*$"
)
CONNECTION_PORT_CLOSED_REGEX = re.compile(
    r"Net-Lib error during Connection refused \(61\)"
)
CONNECTION_HOST_DOWN_REGEX = re.compile(
    r"Net-Lib error during Operation timed out \(60\)"
)


class MssqlEngineSpec(BaseEngineSpec):
    engine = "mssql"
    engine_name = "Microsoft SQL Server"

    metadata = {
        "description": (
            "Microsoft SQL Server is a relational database management system."
        ),
        "logo": "msql.png",
        "homepage_url": "https://www.microsoft.com/en-us/sql-server",
        "categories": [
            DatabaseCategory.TRADITIONAL_RDBMS,
            DatabaseCategory.PROPRIETARY,
        ],
        "pypi_packages": ["pymssql"],
        "connection_string": "mssql+pymssql://{username}:{password}@{host}:{port}/{database}",
        "default_port": 1433,
        "drivers": [
            {
                "name": "pymssql",
                "pypi_package": "pymssql",
                "connection_string": "mssql+pymssql://{username}:{password}@{host}:{port}/{database}",
                "is_recommended": True,
            },
            {
                "name": "pyodbc",
                "pypi_package": "pyodbc",
                "connection_string": "mssql+pyodbc:///?odbc_connect=Driver%3D%7BODBC+Driver+17+for+SQL+Server%7D%3BServer%3Dtcp%3A%3C{host}%3E%2C1433%3BDatabase%3D{database}%3BUid%3D{username}%3BPwd%3D{password}%3BEncrypt%3Dyes%3BConnection+Timeout%3D30",
                "is_recommended": False,
                "notes": (
                    "Connection string must be URL-encoded. "
                    "Special characters like @ need encoding."
                ),
            },
        ],
        "docs_url": "https://docs.sqlalchemy.org/en/20/core/engines.html#escaping-special-characters-such-as-signs-in-passwords",
    }

    max_column_name_length = 128
    allows_cte_in_subquery = False
    supports_multivalues_insert = True

    _time_grain_expressions = {
        None: "{col}",
        TimeGrain.SECOND: "DATEADD(SECOND, \
            DATEDIFF(SECOND, '2000-01-01', {col}), '2000-01-01')",
        TimeGrain.MINUTE: "DATEADD(MINUTE, DATEDIFF(MINUTE, 0, {col}), 0)",
        TimeGrain.FIVE_MINUTES: "DATEADD(MINUTE, \
            DATEDIFF(MINUTE, 0, {col}) / 5 * 5, 0)",
        TimeGrain.TEN_MINUTES: "DATEADD(MINUTE, \
            DATEDIFF(MINUTE, 0, {col}) / 10 * 10, 0)",
        TimeGrain.FIFTEEN_MINUTES: "DATEADD(MINUTE, \
            DATEDIFF(MINUTE, 0, {col}) / 15 * 15, 0)",
        TimeGrain.THIRTY_MINUTES: "DATEADD(MINUTE, \
            DATEDIFF(MINUTE, 0, {col}) / 30 * 30, 0)",
        TimeGrain.HOUR: "DATEADD(HOUR, DATEDIFF(HOUR, 0, {col}), 0)",
        TimeGrain.DAY: "DATEADD(DAY, DATEDIFF(DAY, 0, {col}), 0)",
        TimeGrain.WEEK: "DATEADD(DAY, 1 - DATEPART(WEEKDAY, {col}),"
        " DATEADD(DAY, DATEDIFF(DAY, 0, {col}), 0))",
        TimeGrain.MONTH: "DATEADD(MONTH, DATEDIFF(MONTH, 0, {col}), 0)",
        TimeGrain.QUARTER: "DATEADD(QUARTER, DATEDIFF(QUARTER, 0, {col}), 0)",
        TimeGrain.YEAR: "DATEADD(YEAR, DATEDIFF(YEAR, 0, {col}), 0)",
        TimeGrain.WEEK_STARTING_SUNDAY: "DATEADD(DAY, -1,"
        " DATEADD(WEEK, DATEDIFF(WEEK, 0, {col}), 0))",
        TimeGrain.WEEK_STARTING_MONDAY: "DATEADD(WEEK,"
        " DATEDIFF(WEEK, 0, DATEADD(DAY, -1, {col})), 0)",
    }

    column_type_mappings = (
        (
            re.compile(r"^smalldatetime.*", re.IGNORECASE),
            SMALLDATETIME(),
            GenericDataType.TEMPORAL,
        ),
        (
            re.compile(r"^uniqueidentifier.*", re.IGNORECASE),
            GUID(),
            GenericDataType.STRING,
        ),
    )

    custom_errors: dict[Pattern[str], tuple[str, SupersetErrorType, dict[str, Any]]] = {
        CONNECTION_ACCESS_DENIED_REGEX: (
            __(
                'Either the username "%(username)s", password, '
                'or database name "%(database)s" is incorrect.'
            ),
            SupersetErrorType.CONNECTION_ACCESS_DENIED_ERROR,
            {},
        ),
        CONNECTION_INVALID_HOSTNAME_REGEX: (
            __('The hostname "%(hostname)s" cannot be resolved.'),
            SupersetErrorType.CONNECTION_INVALID_HOSTNAME_ERROR,
            {},
        ),
        CONNECTION_PORT_CLOSED_REGEX: (
            __('Port %(port)s on hostname "%(hostname)s" refused the connection.'),
            SupersetErrorType.CONNECTION_PORT_CLOSED_ERROR,
            {},
        ),
        CONNECTION_HOST_DOWN_REGEX: (
            __(
                'The host "%(hostname)s" might be down, and can\'t be '
                "reached on port %(port)s."
            ),
            SupersetErrorType.CONNECTION_HOST_DOWN_ERROR,
            {},
        ),
    }

    @classmethod
    def epoch_to_dttm(cls) -> str:
        return "dateadd(S, {col}, '1970-01-01')"

    @classmethod
    def convert_dttm(
        cls, target_type: str, dttm: datetime, db_extra: Optional[dict[str, Any]] = None
    ) -> Optional[str]:
        sqla_type = cls.get_sqla_column_type(target_type)

        if isinstance(sqla_type, types.Date):
            return f"CONVERT(DATE, '{dttm.date().isoformat()}', 23)"
        if isinstance(sqla_type, SMALLDATETIME):
            datetime_formatted = dttm.isoformat(sep=" ", timespec="seconds")
            return f"""CONVERT(SMALLDATETIME, '{datetime_formatted}', 20)"""
        if isinstance(sqla_type, types.DateTime):
            datetime_formatted = dttm.isoformat(timespec="milliseconds")
            return f"""CONVERT(DATETIME, '{datetime_formatted}', 126)"""
        return None

    @classmethod
    def fetch_data(
        cls, cursor: Any, limit: Optional[int] = None
    ) -> list[tuple[Any, ...]]:
        if not cursor.description:
            return []
        data = super().fetch_data(cursor, limit)
        # Lists of `pyodbc.Row` need to be unpacked further
        return cls.pyodbc_rows_to_tuples(data)

    @classmethod
    def extract_error_message(cls, ex: Exception) -> str:
        if str(ex).startswith("(8155,"):
            return (
                f"{cls.engine} error: All your SQL functions need to "  # noqa: S608
                "have an alias on MSSQL. For example: SELECT COUNT(*) AS C1 FROM TABLE1"
            )
        return f"{cls.engine} error: {cls._extract_error_message(ex)}"


class AzureSynapseParametersSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)
    server = fields.Str(required=True)
    database = fields.Str(required=True)
    port = fields.Integer(load_default=1433)


class AzureSynapseParametersType(TypedDict, total=False):
    username: str
    password: str
    server: str
    database: str
    port: int


class AzureSynapseSpec(MssqlEngineSpec):
    engine = "mssql"
    engine_name = "Azure Synapse"
    default_driver = "pyodbc"

    metadata = {
        "description": (
            "Azure Synapse Analytics is a cloud-based enterprise data warehouse "
            "from Microsoft that combines big data and data warehousing."
        ),
        "logo": "azure.svg",
        "homepage_url": "https://azure.microsoft.com/en-us/products/synapse-analytics/",
        "categories": [
            DatabaseCategory.CLOUD_DATA_WAREHOUSES,
            DatabaseCategory.ANALYTICAL_DATABASES,
            DatabaseCategory.PROPRIETARY,
        ],
        "pypi_packages": ["pymssql"],
        "connection_string": (
            "mssql+pymssql://{username}@{server}:{password}@"
            "{server}.database.windows.net:1433/{database}"
        ),
    }

    parameters_schema = AzureSynapseParametersSchema()
    sqlalchemy_uri_placeholder = (
        "mssql+pymssql://{username}@{server}:{password}@"
        "{server}.database.windows.net:1433/{database}"
    )

    @classmethod
    def build_sqlalchemy_uri(  # pylint: disable=unused-argument
        cls,
        parameters: AzureSynapseParametersType,
        encrypted_extra: dict[str, str] | None = None,
    ) -> str:
        server = parameters.get("server", "")
        return str(
            URL.create(
                "mssql+pymssql",
                username=f"{parameters.get('username', '')}@{server}",
                password=parameters.get("password"),
                host=f"{server}.database.windows.net",
                port=parameters.get("port", 1433),
                database=parameters.get("database"),
            )
        )

    @classmethod
    def get_parameters_from_uri(  # pylint: disable=unused-argument
        cls,
        uri: str,
        encrypted_extra: dict[str, str] | None = None,
    ) -> AzureSynapseParametersType:
        url = make_url_safe(uri)
        username = url.username or ""
        server = ""
        if "@" in username:
            username, server = username.rsplit("@", 1)
        elif url.host:
            server = url.host.replace(".database.windows.net", "")
        return {
            "username": username,
            "password": url.password,
            "server": server,
            "database": url.database,
            "port": url.port or 1433,
        }

    @classmethod
    def validate_parameters(
        cls, properties: BasicPropertiesType
    ) -> list[SupersetError]:
        errors: list[SupersetError] = []
        required = {"username", "password", "server", "database"}
        parameters = properties.get("parameters", {})
        present = {key for key in parameters if parameters.get(key, ())}

        if missing := sorted(required - present):
            errors.append(
                SupersetError(
                    message=f"One or more parameters are missing: {', '.join(missing)}",
                    error_type=SupersetErrorType.CONNECTION_MISSING_PARAMETERS_ERROR,
                    level=ErrorLevel.WARNING,
                    extra={"missing": missing},
                ),
            )
        return errors

    @classmethod
    def parameters_json_schema(cls) -> Any:
        if not cls.parameters_schema:
            return None

        ma_plugin = MarshmallowPlugin()
        spec = APISpec(
            title="Database Parameters",
            version="1.0.0",
            openapi_version="3.0.0",
            plugins=[ma_plugin],
        )

        spec.components.schema(cls.__name__, schema=cls.parameters_schema)
        return spec.to_dict()["components"]["schemas"][cls.__name__]
