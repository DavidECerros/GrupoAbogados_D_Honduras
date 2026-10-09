from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Model):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class Setup(Login):
    full_name: str = Field(min_length=1, max_length=150)


class Password(Model):
    current_password: str
    new_password: str = Field(min_length=12, max_length=1024)


class Operator(Model):
    username: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=12, max_length=1024)
    entity_ids: list[int] = []


class UserUpdate(Model):
    full_name: str = Field(min_length=1, max_length=150)
    active: bool
    entity_ids: list[int]


class Reset(Model):
    password: str = Field(min_length=12, max_length=1024)


class Entity(Model):
    name: str = Field(min_length=1, max_length=150)
    currency: Literal["HNL", "USD"] = "HNL"
    status: Literal["active", "archived"] = "active"


class Client(Model):
    name: str = Field(min_length=1, max_length=150)
    document_type: str = Field(min_length=1, max_length=50)
    document: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=1, max_length=50)
    email: str = Field(max_length=150, default="")
    notes: str = Field(max_length=2000, default="")


class ClientStatus(Model):
    status: Literal["active", "inactive"]
    reason: str = Field(min_length=3, max_length=2000)


class Lot(Model):
    code: str = Field(min_length=1, max_length=80)
    description: str = Field(max_length=2000, default="")
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Literal["HNL", "USD"] = "HNL"


class Reservation(Model):
    lot_id: int
    client_id: int
    expires_on: date


class Sale(Model):
    lot_id: int
    client_id: int
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Literal["HNL", "USD"]
    down_payment: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    installments: int = Field(gt=0, le=600, strict=True)
    down_due: date
    first_due: date


class Payment(Model):
    operation_id: str = Field(min_length=16, max_length=80)
    contract_id: int
    payment_date: date | None = None
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: Literal["HNL", "USD"]
    method: Literal["cash", "deposit", "transfer"] = "cash"
    bank_reference: str = Field(max_length=150, default="")
    notes: str = Field(max_length=2000, default="")


class Reason(Model):
    reason: str = Field(min_length=3, max_length=2000)


class Transfer(Reason):
    new_client_id: int
    effective_date: date


class Amendment(Reason):
    price: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    down_payment: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    installments: int = Field(gt=0, le=600, strict=True)
    down_due: date
    first_due: date


class Approval(Reason):
    action: Literal["void_payment", "release_reservation", "transfer_contract", "amend_contract"]
    record_id: int
    payload: dict = {}


class Decision(Reason):
    approve: bool


class Settings(Model):
    timezone: str = "America/Tegucigalpa"
    exchange_rate: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=6)
    paper: Literal["letter", "half_letter"] = "letter"
    backup_destination: str = ""
