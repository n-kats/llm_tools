import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
import json
from typing import TypeVar, Type, Generic, Callable, Any

from pydantic import BaseModel, create_model
from jinja2 import Template

T_IN = TypeVar("T_IN", bound=BaseModel)
T_CONTEXT = TypeVar("T_CONTEXT", bound=BaseModel, contravariant=True)
T_OUT = TypeVar("T_OUT")


class Remap(Generic[T_CONTEXT, T_IN]):
    def __init__(self, fn: Callable[[T_CONTEXT], T_IN]):
        self.__fn = fn

    def __call__(self, context: T_CONTEXT) -> T_IN:
        return self.__fn(context)


def _parse(value: str, type_: Type) -> str | BaseModel:
    if issubclass(type_, BaseModel):
        return type_.parse_raw(value)
    else:
        return value


class TypedPrompt(Generic[T_IN, T_OUT]):
    def __init__(
        self,
        template: Template,
        input_type: Type[T_IN],
        output_type: Type[T_OUT]
    ):
        self.__template = template
        self.__input_type = input_type
        self.__output_type = output_type

    @property
    def input_type(self) -> Type[T_IN]:
        return self.__input_type

    @property
    def output_type(self) -> Type[T_OUT]:
        return self.__output_type

    def generate_input(self, input_: T_CONTEXT) -> str:
        assert isinstance(input_, self.__input_type)
        return self.__template.render(_remap(input_.dict(), self.__input_mapping))

    def parse(self, value: str) -> T_OUT:
        return _parse(value, self.__output_type)


@dataclass
class ExecutionState:
    context: BaseModel
    error_count: int

    def add_error(self):
        return replace(self, error_count=self.error_count + 1)

    def update_context(self, context: BaseModel):
        return replace(self, context=context)


class Executer(ABC, Generic[T_IN]):
    def __init__(self, fn: Callable[[str], str], max_retry: int):
        self.__fn = fn
        self.__max_retry = max_retry

    def call(self, input_: str) -> str:
        return self.__fn(input_)

    def build_function(
        self, name: str, remap: Remap, typed_prompt: TypedPrompt, next_type: Type[BaseModel]
    ) -> Callable[[ExecutionState], tuple[Any, ExecutionState]]:
        return self._wrap_base_function(self._build_base_function(
            name, remap, typed_prompt, next_type
        ))

    def _wrap_base_function(self, base_function: Callable[[BaseModel], tuple[Any, BaseModel]]):
        def fn(state: ExecutionState) -> tuple[Any, ExecutionState]:
            for _ in range(state.error_count, self.__max_retry):
                try:
                    result, next_context = base_function(state.context)
                    return result, state.update_context(next_context)
                except Exception:
                    state = state.add_error()
            raise Exception("Too many errors")
        return fn

    def _build_base_function(
        self, name: str, remap: Remap,
        typed_prompt: TypedPrompt, next_type: Type[BaseModel],
    ) -> Callable[[BaseModel], Any]:
        def fn(context: BaseModel) -> Any:
            remapped = remap(context)
            assert isinstance(remapped, typed_prompt.input_type)
            result = typed_prompt.parse(
                self.call(typed_prompt.generate_input(remapped)))
            next_context = next_type(
                **{name: result}, **context.dict())
            return result, next_context
        return fn


class Tactic:
    def __init__(
            self, input_type: Type[BaseModel],
            functions: list[
                Callable[[ExecutionState], tuple[Any, ExecutionState]]]
    ):
        self.__input_type = input_type
        self.__functions = functions

    def __call__(self, context: BaseModel) -> tuple[Any, ExecutionState]:
        assert isinstance(context, self.__input_type)
        state = ExecutionState(context, 0)
        for fn in self.__functions:
            result, state = fn(state)
        return result, state


class TacticBuilder:
    def __init__(self, name: str, input_type: Type[T_IN]):
        self.__typed_prompts: dict[str, TypedPrompt] = {}
        self.__current_context_type = create_model(
            f"_InputContextType_{name}", input=input_type)
        self.__functions: list[Callable[[BaseModel], Any]] = []

    def add_typed_prompt(self, name: str, remap: Remap, typed_prompt: TypedPrompt, excecuter: Executer):
        assert name not in self.__typed_prompts
        self.__typed_prompts[name] = typed_prompt
        next_context_type = create_model(
            f"_ContextTypeAfter_{name}", **{name: typed_prompt.output_type},
            __base__=self.__current_context_type)
        self.__functions.append(excecuter.build_function(
            name, remap, typed_prompt, next_context_type))
        self.__current_context_type = next_context_type

    def show_typed_prompts(self, file=sys.stdout):
        for name, typed_prompt in self.__typed_prompts.items():
            print(f"""[{name}.input_type]
{typed_prompt.input_type}

[{name}.output_type]
typed_prompt.output_type
""", file=file)

    def build(self):
        return Tactic(self.__input_type, self.__functions.copy())
