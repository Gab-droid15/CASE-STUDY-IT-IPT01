from typing import Annotated, Literal
from pydantic import BaseModel, Field, StringConstraints

# strip_whitespace removes the extra spaces, then the length is checked
ProductName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=25)]
CustomerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


# ---------- Customer side ----------
class OrderItemInput(BaseModel):
    product_id: int
    qty: int = Field(gt=0)
    gallon_type: Literal["Round", "Slim"] | None = None   # only needed for water refills


class OrderInput(BaseModel):
    customer_name: CustomerName
    items: list[OrderItemInput] = Field(min_length=1)      # at least 1 item
    cash: float = Field(gt=0)


# ---------- Owner side ----------
class OwnerLoginInput(BaseModel):
    password: str


class ProductInput(BaseModel):                             # used when ADDING a product
    name: ProductName
    price: float = Field(gt=0)
    stock: int | None = Field(default=None, ge=0)          # None = water (no stock count)


class ProductUpdateInput(BaseModel):                       # used when UPDATING (all optional)
    name: ProductName | None = None
    price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    available: bool | None = None                          # water only
