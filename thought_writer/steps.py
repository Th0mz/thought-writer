# TODO
# The most part of our work will be in using the right prompts, and the
# prompts are called in this file. So, we will need to change it once we've
# come up with our prompts, so that it uses our logic.

import inspect
import json
import re
import subprocess

from enum import Enum
from typing import List

from termcolor import colored

from thought_writer.ai import AI
#from thought_writer.chat_to_files import to_files
from thought_writer.db import DBs
#from thought_writer.learning import human_input


def setup_sys_prompt(dbs: DBs) -> str:
    return (
        dbs.preprompts["generate"] + "\nUseful to know:\n" + dbs.preprompts["philosophy"]
    )


def get_prompt(dbs: DBs) -> str:
    """While we migrate we have this fallback getter"""
    assert (
        "prompt" in dbs.input or "main_prompt" in dbs.input
    ), "Please put your prompt in the file `prompt` in the ideas directory"

    if "prompt" not in dbs.input:
        print(
            colored("Please put the prompt in the file `prompt`, not `main_prompt", "red")
        )
        print()
        return dbs.input["main_prompt"]

    return dbs.input["prompt"]


def curr_fn() -> str:
    """Get the name of the current function"""
    return inspect.stack()[1].function


# All steps below have the signature Step


def simple_idea(ai: AI, dbs: DBs) -> List[dict]:
    """
    Run the AI on the main prompt
    """
    messages = ai.start(setup_sys_prompt(dbs), get_prompt(dbs), step_name=curr_fn())
    
    return messages


def clarify(ai: AI, dbs: DBs) -> List[dict]:
    """
    Ask the user if they want to clarify anything
    """
    messages = [ai.fsystem(dbs.preprompts["qa"])]
    user_input = get_prompt(dbs)
    while True:
        messages = ai.next(messages, user_input, step_name=curr_fn())

        if messages[-1]["content"].strip() == "Nothing more to clarify.":
            break

        if messages[-1]["content"].strip().lower().startswith("no"):
            print("Nothing more to clarify.")
            break

        print()
        user_input = input('(answer in text, or "c" to move on)\n')
        print()

        if not user_input or user_input == "c":
            print("(letting thought-writer make its own assumptions)")
            print()
            messages = ai.next(
                messages,
                "Make your own assumptions and state them explicitly before starting",
                step_name=curr_fn(),
            )
            print()
            return messages

        user_input += (
            "\n\n"
            "Is the idea fully specified? If no, only answer in the form:\n"
            "{Next question}\n"
            'If the idea is fully specified, only answer "Nothing more to clarify.".'
        )

    print()
    return messages

def gen_spec(ai: AI, dbs: DBs) -> List[dict]:
    """
    Generate a description from the main prompt + clarifications
    """
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fsystem(f"Instructions: {dbs.input['prompt']}"),
    ]

    messages = ai.next(messages, dbs.preprompts["desc"], step_name=curr_fn())

    dbs.memory["description"] = messages[-1]["content"]

    return messages


def review_spec(ai: AI, dbs: DBs) -> List[dict]:
    messages = json.loads(dbs.logs[gen_spec.__name__])
    messages += [ai.fsystem(dbs.preprompts["review_spec"])]

    messages = ai.next(messages, step_name=curr_fn())
    messages = ai.next(
        messages,
        (
            "Based on the conversation so far, please reiterate the description for "
            "the idea. "
            "If there are things that can be improved, please incorporate the "
            "improvements. "
            "If you are satisfied with the description, just write out the "
            "description word by word again."
        ),
        step_name=curr_fn(),
    )

    dbs.memory["description"] = messages[-1]["content"]
    return messages

def gen_clarified_thought(ai: AI, dbs: DBs) -> List[dict]:
    """Takes clarification and generates a structured thought"""
    messages = json.loads(dbs.logs[clarify.__name__])

    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
    ] + messages[1:]
    messages = ai.next(messages, dbs.preprompts["layout_idea"], step_name=curr_fn())

    return messages


def give_idea(ai: AI, dbs: DBs) -> List[dict]:
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fuser(f"Instructions: {dbs.input['prompt']}"),
        ai.fuser(f"Specification:\n\n{dbs.memory['description']}"),
    ]
    messages = ai.next(messages, dbs.preprompts["layout_idea"], step_name=curr_fn())
    
    return messages

def use_feedback(ai: AI, dbs: DBs):
    messages = [
        ai.fsystem(setup_sys_prompt(dbs)),
        ai.fuser(f"Instructions: {dbs.input['prompt']}"),
        ai.fassistant(dbs.workspace["all_output.txt"]),
        ai.fsystem(dbs.preprompts["use_feedback"]),
    ]
    messages = ai.next(messages, dbs.input["feedback"], step_name=curr_fn())
    
    return messages

def human_review(ai: AI, dbs: DBs):
    #review = human_input()
    #dbs.memory["review"] = review.to_json()  # type: ignore
    return []


class Config(str, Enum):
    DEFAULT = "default"
    BENCHMARK = "benchmark"
    SIMPLE = "simple"
    TDD = "tdd"
    TDD_PLUS = "tdd+"
    CLARIFY = "clarify"
    RESPEC = "respec"
    EXECUTE_ONLY = "execute_only"
    EVALUATE = "evaluate"
    USE_FEEDBACK = "use_feedback"


# Different configs of what steps to run
STEPS = {
    Config.DEFAULT: [
        clarify,
        gen_clarified_thought,
        #human_review,
    ],
    Config.SIMPLE: [simple_idea, ],
    Config.TDD: [
        gen_spec,
        give_idea,
        #human_review,
    ],
    Config.RESPEC: [
        gen_spec,
        review_spec,
        give_idea,
        #human_review,
    ],
    Config.USE_FEEDBACK: [use_feedback, ], #[use_feedback, human_review],
    Config.EVALUATE: [], #[human_review],
}

# Future steps that can be added:
# run_tests_and_fix_files
# execute_entrypoint_and_fix_files_if_it_results_in_error
