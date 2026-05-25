# Visual Programming

FoundryUI represents a biomolecular design pipeline as a graph. Each node is a visible operation with typed ports. A connection means that the output artifact from one operation becomes the input artifact of another.

This model keeps the workflow inspectable:

- You can see every transformation from upload to final save.
- Intermediate files are persisted in the run directory.
- Manual selector nodes pause only when their upstream inputs are available.
- Scores and structures move together so filtering does not break alignment.

The graph is not just a diagram. During a run, the backend executes the graph, streams command output, stores artifacts, and reports node status back to the frontend.
