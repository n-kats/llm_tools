import os

import click


def _upper(name: str):
    return name.upper().replace("-", "_")


def set_completions_command(name: str, command: click.Group):
    @command.command()
    @click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
    def completions(shell: str):
        f"""補間機能用コマンド。

        zshの場合、次の方法で補間が有効になる。

        $ {name} completions zsh > ~/.zfunc/_{name}


        """
        os.environ[f"_{_upper(name)}_COMPLETE"] = f"{shell}_source"
        command()
