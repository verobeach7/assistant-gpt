import streamlit as st
import openai
import json
from openai import OpenAI
from langchain.utilities import WikipediaAPIWrapper
from langchain.schema import SystemMessage
from langchain.document_loaders import WebBaseLoader
from langchain.tools import DuckDuckGoSearchResults
from langchain.tools import WikipediaQueryRun
from typing_extensions import override
from openai import AssistantEventHandler


def duckduckgo_search(inputs):
    ddg = DuckDuckGoSearchResults()
    query = inputs["query"]
    try:
        ddg_results = ddg.run(query)
        if not ddg_results:
            print("No result returned.")
        else:
            print("ddg!!!!!!!!!!!!!!!!!!!!!!!!!!ddg\n", ddg_results)
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
    return ddg_results


def wikipedia_search(inputs):
    wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
    query = inputs["query"]
    wiki_results = wiki.run(query)
    print("wiki!!!!!!!!!!!!!!!!!!!!!!!!!!!!wiki\n", wiki_results)
    return wiki_results


def web_scraping(inputs):
    urls = inputs["urls"]
    loader = WebBaseLoader([urls])
    docs = loader.load()
    text = "\n\n".join([doc.page_content for doc in docs]).replace("\n", "")
    return text


def save_to_txt(inputs):
    text = inputs["text"]
    print(text)
    query = inputs["query"]
    file_path = f"research_results_{query}.txt"
    with open(file_path, "w") as file:
        file.write(text)

    return f"Research results saved to {file_path}"


functions_map = {
    "duckduckgo_search": duckduckgo_search,
    "wikipedia_search": wikipedia_search,
    "web_scraping": web_scraping,
    "save_to_txt": save_to_txt,
}


functions = [
    {
        "type": "function",
        "function": {
            "name": "duckduckgo_search",
            "description": """
                Use this tool to perform web searches using the DuckDuckGo search engine.
                It takes a query as an argument.
                Example query: "Latest technology news"
                """,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query you will search for",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia_search",
            "description": """
                Use this tool to perform searches on Wikipedia.
                It takes a query as an argument.
                Example query: "Artificial Intelligence"
                """,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query you will search for",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_scraping",
            "description": """
                If you found the website link in DuckDuckGo,
                Use this to get the content of the link for my research.
                """,
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "string",
                        "description": "The URL of the website you want to scrape",
                    }
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_txt",
            "description": "Use this tool to save the content as a .txt file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text you will save to a file.",
                    },
                    "query": {
                        "type": "string",
                        "description": "The query you will search for",
                    },
                },
                "required": ["text", "query"],
            },
        },
    },
]

assistant_name = "Research Assistant"


# Streamlit


# API 키 유효성 검사 함수
def validate_openai_api_key(api_key):
    try:
        openai.api_key = api_key
        # openai.Model.list()
        openai.models.list()
        return True
    except openai.AuthenticationError:
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return False


st.set_page_config(
    page_title=f"{assistant_name}",
    page_icon="🔍",
)

st.title(f"{assistant_name}")

st.markdown(
    """
    This GPT uses DuckDuckGo and Wikipedia to research whatever you want to know. It summarizes the gathered information for you and provides a file containing the details from the referenced sources.
    """
)


def main():
    class EventHandler(AssistantEventHandler):
        message = ""

        @override
        def on_text_created(self, text) -> None:
            self.message_box = st.empty()

        def on_text_delta(self, delta, snapshot):
            self.message += delta.value
            self.message_box.markdown(self.message.replace("$", "\$"))

        @override
        def on_event(self, event):
            # Retrieve events that are denoted with 'requires_action'
            # since these will have our tool_calls
            if event.event == "thread.run.requires_action":
                run_id = event.data.id  # Retrieve the run ID from the event data
                self.handle_requires_action(event.data, run_id)

        def handle_requires_action(self, data, run_id):
            tool_outputs = []

            for tool in data.required_action.submit_tool_outputs.tool_calls:
                tool_id = tool.id
                function = tool.function
                print(
                    f"Calling function: {function.name} with arg {function.arguments}"
                )
                tool_outputs.append(
                    {
                        "output": functions_map[function.name](
                            json.loads(function.arguments)
                        ),
                        "tool_call_id": tool_id,
                    }
                )

            # Submit all tool_outputs at the same time
            self.submit_tool_outputs(tool_outputs, run_id)

        def submit_tool_outputs(self, tool_outputs, run_id):
            # Use the submit_tool_outputs_stream helper
            with client.beta.threads.runs.submit_tool_outputs_stream(
                thread_id=self.current_run.thread_id,
                run_id=self.current_run.id,
                tool_outputs=tool_outputs,
                event_handler=EventHandler(),
            ) as stream:
                for text in stream.text_deltas:
                    print(text, end="", flush=True)
                print()

    # Utility Functions

    # Thread 실행
    def get_run(run_id, thread_id):
        return client.beta.threads.runs.retrieve(
            run_id=run_id,
            thread_id=thread_id,
        )

    # Thread에 메시지 보내기
    def send_message(thread_id, content):
        return client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content,
        )

    # Thread에 있는 메시지 받기
    def get_messages(thread_id):
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        messages = list(messages)
        messages.reverse()
        return messages

    # Chat Message
    def show_chat(role, message):
        with st.chat_message(role):
            st.markdown(message)

    # Paint History
    def paint_history(thread_id):
        messages = get_messages(thread_id)
        for message in messages:
            show_chat(
                message.role,
                message.content[0].text.value,
            )

    if openai_api_key:
        st.write(
            "##### Step 2. Enter the topic you want to research in the input field below"
        )
        client = OpenAI()

        if "assistant" not in st.session_state:
            assistants = client.beta.assistants.list()
            for assistant in assistants:
                # OpenAI에 이미 만들어준 Research Assistant가 있는지 확인
                if assistant.name == assistant_name:
                    assistant = client.beta.assistants.retrieve(assistant.id)
                    print("Bringed the assistant from my OpenAI")
                    break
                else:
                    assistant = client.beta.assistants.create(
                        name="Research Assistant",
                        instructions="""
                            You are a research expert.

                            Your task is to use Wikipedia or DuckDuckGo to gather comprehensive and accurate information about the query provided.

                            When you find a relevant website through DuckDuckGo, you must scrape the content from that website. Use this scraped content to thoroughly research and formulate a detailed answer to the question.

                            Combine information from Wikipedia, DuckDuckGo searches, and any relevant websites you find. Ensure that the final answer is well-organized and detailed, and include citations with links (URLs) for all sources used.

                            Your research should be saved to a .txt file, and the content should match the detailed findings provided. Make sure to include all sources and relevant information.

                            The information from Wikipedia must be included.

                            Ensure that the final .txt file contains detailed information, all relevant sources, and citations.
                            """,
                        model="gpt-4o-mini",
                        tools=functions,
                    )
                    print("Created a assistant")
                    break
            print("Assistant name: ", assistant.name)
            print("Assistant ID: ", assistant.id)
            st.session_state["assistant"] = assistant
            print("Put the assistant in session state")
            thread = client.beta.threads.create()
            st.session_state["thread"] = thread
            print("Put the thread in session state")

        else:
            assistant = st.session_state["assistant"]
            print("Assistant name: ", assistant.name)
            print("Assistant ID: ", assistant.id)
            print("use assistant in session state")
            thread = st.session_state["thread"]
            print("use thread in session state")

        paint_history(thread.id)

        query = st.chat_input("Write down the topic you want to research")

        if query:
            send_message(thread.id, query)
            show_chat("user", query)

            with st.chat_message("assistant"):
                with st.spinner("In progress..."):
                    with client.beta.threads.runs.stream(
                        thread_id=thread.id,
                        assistant_id=assistant.id,
                        event_handler=EventHandler(),
                    ) as stream:
                        stream.until_done()
                    file_path = f"research_results_{query}.txt"
                    with open(file_path, "rb") as f:
                        st.download_button(
                            f"Download {file_path}",
                            f,
                            file_name=f"{file_path}",
                            mime="text/plain",
                        )
    else:
        st.write("##### Step 1. Add your OpenAI API Key")


with st.sidebar:
    openai_api_key = st.text_input(
        "OpenAI API Key", type="password", placeholder="Add your OpenAI API Key"
    )

    if openai_api_key:
        if openai_api_key:
            if validate_openai_api_key(openai_api_key):
                st.success("Your API Key is valid!")
            else:
                st.error("Invalid OpenAI API Key. Please check and try again.")
    st.link_button(
        "GitHub Repo",
        "https://github.com/verobeach7/assistant-gpt/commits/main/",
    )

try:
    main()
except Exception as e:
    st.error("Something wrong. Refresh the site!")
    st.write(e)
