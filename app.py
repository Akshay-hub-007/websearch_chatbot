from typing import  Annotated,Optional,TypedDict
from langgraph.graph import StateGraph,START,END,add_messages
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.checkpoint.memory import MemorySaver
from fastapi.responses import StreamingResponse
from uuid import uuid4
import json
from langchain_core.messages import BaseMessage,AIMessage,HumanMessage,ToolMessage,AIMessageChunk
from dotenv import load_dotenv
from fastapi import FastAPI,Query
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()
model=ChatGoogleGenerativeAI(model="gemini-1.5-flash")
load_dotenv()

# Initialize memory saver for checkpointing
memory=MemorySaver()
class State(TypedDict):
    messages: Annotated[list, add_messages]

search_tool = TavilySearchResults(
    max_results=4,
)

tools = [search_tool]

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

llm_with_tools = llm.bind_tools(tools=tools)

async def model(state: State):
    result = await llm_with_tools.ainvoke(state["messages"])
    return {
        "messages": [result], 
    }

async def tools_router(state: State):
    last_message = state["messages"][-1]

    if(hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0):
        return "tool_node"
    else: 
        return END
    
async def tool_node(state):
    """Custom tool node that handles tool calls from the LLM."""
    # Get the tool calls from the last message
    tool_calls = state["messages"][-1].tool_calls
    
    # Initialize list to store tool messages
    tool_messages = []
    
    # Process each tool call
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        # Handle the search tool
        if tool_name == "tavily_search_results_json":
            # Execute the search tool with the provided arguments
            search_results = await search_tool.ainvoke(tool_args)
            
            # Create a ToolMessage for this result
            tool_message = ToolMessage(
                content=str(search_results),
                tool_call_id=tool_id,
                name=tool_name
            )
            
            tool_messages.append(tool_message)
    
    # Add the tool messages to the state
    return {"messages": tool_messages}


graph_builder = StateGraph(State)

graph_builder.add_node("model", model)
graph_builder.add_node("tool_node", tool_node)
graph_builder.set_entry_point("model")

graph_builder.add_conditional_edges("model", tools_router)
graph_builder.add_edge("tool_node", "model")

graph = graph_builder.compile(checkpointer=memory)


app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type"]
)


def serialise_ai_message_chunk(chunk): 
    if(isinstance(chunk, AIMessageChunk)):
        return chunk.content
    else:
        raise TypeError(
            f"Object of type {type(chunk).__name__} is not correctly formatted for serialisation"
        )

async def generate_chat_response(message,checkpoint_id):

    is_new_conversation=checkpoint_id is None

    if is_new_conversation:

        new_checkpoint_id=uuid4()

        config={
            "configurable":{
                "thread_id":1
            }
        }

        events=graph.astream_events(
           {"messages": HumanMessage(content=message)},
            version="v2",
            config=config
        )

        yield f"data: {{\"type\": \"checkpoint\", \"checkpoint_id\": \"{new_checkpoint_id}\"}}\n\n"
    else:

        config={
            "configurable":{
                "thread_id":checkpoint_id
            }
        }
        events = graph.astream_events(
            {"messages": [HumanMessage(content=message)]},
            version="v2",
            config=config
        )

    async for event in events:
        event_name=event["event"]
        # print(event_name)
        if event_name=="on_chat_model_stream":
            # print()
            chunk_content=serialise_ai_message_chunk(event["data"]["chunk"])
            print(chunk_content)
            safe_content= chunk_content.replace("'", "\\'").replace("\n", "\\n")
            
            yield f"data: {{\"type\": \"content\", \"content\": \"{safe_content}\"}}\n\n"

        elif event_name=="on_chat_model_end":
            print(event_name)
            tool_calls=event["data"]["output"].tool_calls if hasattr(event["data"]["output"],"tool_calls") else []
            print(tool_calls)
            search_calls=[call for call in tool_calls if call["name"]=="tavily_search_results_json"]
            if search_calls:
                search_query = search_calls[0]["args"].get("query", "")
                safe_query = search_query.replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")
                print(safe_query)
                yield f"data: {{\"type\": \"search_start\", \"query\": \"{safe_query}\"}}\n\n"
        
        elif event_name == "on_tool_end" and event["name"] == "tavily_search_results_json":
            # Search completed - send results or error
            output = event["data"]["output"]
            # Check if output is a list 
            if isinstance(output, list):
                # Extract URLs from list of search results
                # print(output)
                urls = []
                for item in output:
                    if isinstance(item, dict) and "url" in item:
                        urls.append(item["url"])
                # print(urls)
                # Convert URLs to JSON and yield them
                urls_json = json.dumps(urls)
                yield f"data: {{\"type\": \"search_results\", \"urls\": {urls_json}}}\n\n"
    yield f"data: {{\"type\": \"end\"}}\n\n"



@app.get("/chat_stream/{message}")
async def chat_stream(message:str,checkpoint_id:Optional[str]=Query(None)):

    return StreamingResponse(
        generate_chat_response(message,checkpoint_id),
        media_type="text/event-stream"
    )