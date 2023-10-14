import pdb
from typing import Type, TypeVar, Any, Callable, Generic
from pydantic.config import ConfigDict
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod
import openai


class APICaller(ABC):
    @abstractmethod
    def call_api(self, prompt):
        pass


class CostCounter:
    def __init__(self, target: str, unit: str):
        self.__target = target
        self.__unit = unit


class Foo(BaseModel):
    foo: str = Field(..., description="foo")
    bar: str = Field(..., description="bar")


T = TypeVar("T", bound=BaseModel, contravariant=True)


class FunctionCallingFunction(Generic[T]):
    def __init__(self, name: str, description: str, parameter_type: Type[T], function: Callable[[T], Any]):
        self.__name = name
        self.__description = description
        self.__parameter_type = parameter_type
        self.__function = function

    @property
    def name(self):
        return self.__name

    @property
    def description(self):
        return self.__description

    def parameter_schema(self):
        return self.__parameter_type.model_json_schema()

    def __call__(self, parameter: Any):
        return self.__function(self.__parameter_type(**parameter))


def function_calling(name=None, description=None):
    def decorator(func):
        assert len(func.__annotations__) == 1
        type_ = list(func.__annotations__.values())[0]
        assert issubclass(type_, BaseModel)

        return FunctionCallingFunction(name=name or func.__name__, description=description or func.__doc__, parameter_type=type_, function=func)
    return decorator


@function_calling(description="bar")
def foo(data: Foo):
    pass


pdb.set_trace()
print(foo)
