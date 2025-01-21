# backend/api/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

# Define our basic state type
class State(TypedDict):
    messages: List[Dict]
    context: Dict

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create basic graph
graph_builder = StateGraph(State)

# Basic message processor
async def process_message(state: State) -> State:
    """Basic message processor that just echoes back"""
    if state["messages"]:
        last_message = state["messages"][-1]
        return {
            "messages": state["messages"] + [
                {
                    "role": "assistant",
                    "content": f"Received: {last_message['content']}"
                }
            ],
            "context": state["context"]
        }
    return state

# Add nodes to graph
graph_builder.add_node("processor", process_message)
graph_builder.add_edge(START, "processor")
graph_builder.add_edge("processor", END)

# Compile graph
graph = graph_builder.compile()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Initialize state
            initial_state = {
                "messages": [{"role": "user", "content": data["message"]}],
                "context": {}
            }
            
            # Process through graph
            result = await graph.arun(initial_state)
            
            # Send response back to client
            await websocket.send_json({
                "type": "response",
                "data": result
            })
    except Exception as e:
        print(f"Error: {e}")
    finally:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)