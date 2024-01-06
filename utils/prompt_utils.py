import re
import sys
from abc import ABC
from pathlib import Path
from dataclasses import dataclass, replace
import json
from typing import TypeVar, Type, Generic, Callable, Any, Optional, cast
import traceback

import openai
from pydantic import BaseModel, create_model
from jinja2 import Environment, FileSystemLoader, Template

T_IN = TypeVar("T_IN", bound=BaseModel)
T_CONTEXT = TypeVar("T_CONTEXT", bound=BaseModel, contravariant=True)
T_OUT = TypeVar("T_OUT")


class Adapter(Generic[T_CONTEXT, T_IN]):
    def __init__(self, fn: Callable[[T_CONTEXT], T_IN]):
        self.__fn = fn

    def __call__(self, context: T_CONTEXT) -> T_IN:
        return self.__fn(context)

    @staticmethod
    def identity(type_: Type[T_IN]) -> "Adapter[T_IN, T_IN]":
        def fn(x: T_IN) -> T_IN:
            return x

        return Adapter[T_IN, T_IN](fn)

    @classmethod
    def project(cls, type_to: Type[T_IN]) -> "Adapter[T_CONTEXT, T_IN]":
        def fn(x: T_CONTEXT) -> T_IN:
            return type_to(**{key: getattr(x, key) for key in type_to.model_fields})

        return cls(fn)

    @classmethod
    def field(cls, field_name: str, type_: Type[T_IN]) -> "Adapter[T_CONTEXT, T_IN]":
        def fn(x: T_CONTEXT) -> T_IN:
            value = getattr(x, field_name)
            assert isinstance(value, type_)
            return value

        return cls(fn)


def fix_json(text: str) -> str:
    return re.sub(r'(\\[^"])', r"\\\1", text)


def _parse(value: str, type_: Type) -> str | BaseModel:
    if issubclass(type_, BaseModel):
        try:
            json.loads(value)
        except json.JSONDecodeError:
            value = fix_json(value)

        try:
            return type_.parse_raw(value)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSONデコードエラー\n[元データ]{value}") from e
        except Exception as e:
            raise RuntimeError(
                f"パースエラー\n[元データ]{value}\n\n[期待されるフィールド] {list(type_.model_fields.keys())}"
            ) from e
    else:
        return value


class TypedPrompt(Generic[T_IN, T_OUT]):
    def __init__(
        self, template: Template, input_type: Type[T_IN], output_type: Type[T_OUT]
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
        return self.__template.render(**input_.dict())

    def parse(self, value: str) -> T_OUT:
        return cast(T_OUT, _parse(value, self.__output_type))


def load_template(
    template_path: Path, template_root: Optional[Path] = None
) -> Template:
    if template_root is None:
        template_root = template_path.parent
        template_path = Path(template_path.name)
    env = Environment(loader=FileSystemLoader(template_root, encoding="utf8"))
    return env.get_template(str(template_path))


@dataclass
class ExecutionState:
    context: BaseModel
    error_count: int

    def add_error(self):
        return replace(self, error_count=self.error_count + 1)

    def update_context(self, context: BaseModel):
        return replace(self, context=context)


class Executor(ABC, Generic[T_IN]):
    def __init__(self, fn: Callable[[str], str], max_retry: int):
        self.__fn = fn
        self.__max_retry = max_retry

    def build_function(
        self,
        name: str,
        adapter: Adapter,
        typed_prompt: TypedPrompt,
        next_type: Type[BaseModel],
    ) -> Callable[[ExecutionState], tuple[Any, ExecutionState]]:
        return self._wrap_base_function(
            self._build_base_function(name, adapter, typed_prompt, next_type)
        )

    def _wrap_base_function(
        self, base_function: Callable[[BaseModel], tuple[Any, BaseModel]]
    ):
        def fn(state: ExecutionState) -> tuple[Any, ExecutionState]:
            for _ in range(state.error_count, self.__max_retry):
                try:
                    result, next_context = base_function(state.context)
                    return result, state.update_context(next_context)
                except Exception:
                    traceback.print_exc()
                    state = state.add_error()
            raise Exception("Too many errors")

        return fn

    def _build_base_function(
        self,
        name: str,
        adapter: Adapter,
        typed_prompt: TypedPrompt,
        next_type: Type[BaseModel],
    ) -> Callable[[BaseModel], Any]:
        def fn(context: BaseModel) -> Any:
            input_ = adapter(context)
            assert isinstance(input_, typed_prompt.input_type)
            result = typed_prompt.parse(self.__fn(typed_prompt.generate_input(input_)))
            next_context = next_type(**{name: result}, **context.dict())
            return result, next_context

        return fn


class Tactic:
    def __init__(
        self,
        input_type: Type[BaseModel],
        output_type: Type[BaseModel] | Type[str],
        functions: list[Callable[[ExecutionState], tuple[Any, ExecutionState]]],
    ):
        self.__input_type = input_type
        self.__output_type = output_type
        self.__functions = functions

    @property
    def input_type(self) -> Type[BaseModel]:
        return self.__input_type

    @property
    def output_type(self) -> Type[BaseModel] | Type[str]:
        return self.__output_type

    def __call__(self, context: BaseModel) -> tuple[Any, ExecutionState]:
        assert isinstance(context, self.__input_type)
        state = ExecutionState(context, 0)
        for fn in self.__functions:
            result, state = fn(state)
        return result, state


def type_to_preview(type_: Type) -> str:
    if issubclass(type_, BaseModel):
        return json.dumps(type_.model_json_schema(), indent=2)
    else:
        return type_.__name__


class TacticBuilder:
    def __init__(self, name: str, input_type: Type[T_IN]):
        self.__typed_prompts: dict[str, TypedPrompt] = {}
        self.__input_type = input_type
        self.__current_context_type = input_type
        self.__functions: list[
            Callable[[ExecutionState], tuple[ExecutionState, Any]]
        ] = []

    def add_typed_prompt(
        self, name: str, adapter: Adapter, typed_prompt: TypedPrompt, executor: Executor
    ):
        assert name not in self.__typed_prompts
        self.__typed_prompts[name] = typed_prompt
        next_context_type = create_model(
            f"_ContextTypeAfter_{name}",
            **{name: (typed_prompt.output_type, None)},
            __base__=self.__current_context_type,
        )  # type: ignore
        self.__functions.append(
            executor.build_function(name, adapter, typed_prompt, next_context_type)
        )
        self.__current_context_type = next_context_type

    def show_typed_prompts(self, file=sys.stdout):
        print(
            f"""[input_type]
{type_to_preview(self.__input_type)}
""",
            file=file,
        )

        print(
            f"""[output_type]
{type_to_preview(self.__current_context_type)}
""",
            file=file,
        )

        for name, typed_prompt in self.__typed_prompts.items():
            print(
                f"""[{name}.input_type]
{type_to_preview(typed_prompt.input_type)}

[{name}.output_type]
{type_to_preview(typed_prompt.output_type)}
""",
                file=file,
            )

    def get_current_context_type(self) -> Type[BaseModel]:
        return self.__current_context_type

    def build(self):
        return Tactic(
            input_type=self.__input_type,
            output_type=self.__current_context_type,
            functions=self.__functions.copy(),
        )


def call_gpt(text, model="gpt-3.5-turbo"):
    completion = openai.ChatCompletion.create(
        model=model, messages=[{"role": "user", "content": text}]
    )
    return completion.choices[0].message.content
