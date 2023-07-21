import json
import logging

from pathlib import Path

import typer

from thought_writer.ai import AI, fallback_model
#from thought_writer.collect import collect_learnings
from thought_writer.db import DB, DBs, archive
#from thought_writer.learning import collect_consent
from thought_writer.steps import STEPS, Config as StepsConfig
from os import mkdir

app = typer.Typer()


@app.command()
def main(
    model: str = typer.Argument("gpt-4", help="model id string"),
    temperature: float = 0.1,
    steps_config: StepsConfig = typer.Option(
        StepsConfig.DEFAULT, "--steps", "-s", help="decide which steps to run"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):

    idea_prompt = input("What is your idea?\n > ")
    idea_name = input("Name you idea:\n > ")
    idea_path = "ideas/" + idea_name
    
    mkdir(idea_path)
    with open(idea_path + "/prompt", "w+") as prompt_file:
        prompt_file.write(idea_prompt)

    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    model = fallback_model(model)
    ai = AI(
        model=model,
        temperature=temperature,
    )

    input_path = Path(idea_path).absolute()
    memory_path = input_path / "memory"
    workspace_path = input_path / "workspace"
    archive_path = input_path / "archive"

    dbs = DBs(
        memory=DB(memory_path),
        logs=DB(memory_path / "logs"),
        input=DB(input_path),
        workspace=DB(workspace_path),
        preprompts=DB(Path(__file__).parent / "preprompts"),
        archive=DB(archive_path),
    )

    if steps_config not in [
        StepsConfig.EXECUTE_ONLY,
        StepsConfig.USE_FEEDBACK,
        StepsConfig.EVALUATE,
    ]:
        archive(dbs)

    steps = STEPS[steps_config]
    last_message = None
    for step in steps:
        messages = step(ai, dbs)
        dbs.logs[step.__name__] = json.dumps(messages)
        last_message = messages

    with open(idea_path + "/result", "w+") as result_file:
        result_file.write(last_message[-1]['content'])

    #if collect_consent():
    #    collect_learnings(model, temperature, steps, dbs)

    dbs.logs["token_usage"] = ai.format_token_usage_log()


if __name__ == "__main__":
    app()
