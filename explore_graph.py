from pyvis.network import Network
import json

data = json.load(open("outputs/graph.json"))
net = Network(height="800px", width="100%", directed=True)

colors = {
    "Paper": "#4e79a7",
    "Species": "#59a14f",
    "VocalisationType": "#f28e2b",
    "BehaviouralContext": "#e15759",
    "CommunicationFunction": "#b07aa1",
    "AnalysisMethod": "#76b7b2",
    "DatasetResource": "#edc948",
}

for node in data["nodes"]:
    label = node.get("label", "")
    net.add_node(node["id"], label=node.get("name") or node.get("title") or node["id"],
                 color=colors.get(label, "#aaa"), title=label)

for edge in data.get("edges") or data.get("links", []):
    net.add_edge(edge["source"], edge["target"], title=edge.get("relation", ""))

net.show("outputs/graph.html", notebook=False)