
### Fix
- Rosetta Fold 3 node input should be able to receive multiple ligands(by receiving mutiple lines) for co-folding.
- Once the user manually processed the stuck nodes, they should not pop up when the page is refreshed. Also the content user inputted should be preserved in the session. Now the content losses after refresh.
- Remove the simple Document built in the frontend

### Add
- Add a documentation site for this project:

Use docsify: https://docsify.js.org/ to host the markdowns
Do not add the dependencies and hosting of document to normal installtion, keep them separate.
Use the dark theme: <link rel="stylesheet" href="//cdn.jsdelivr.net/npm/docsify/lib/themes/dark.css" />

Your markdown structure should look like this:
- Install
  - Installtion script
  - Images (leave blank)
- Principles
  - Visual programming
  - Concepts
    - Nodes
    - Types
    - Flow
    - Loads
    - Saves
- Nodes
  - Filter
    - Filter Chain
    - Score Filter
    - ...
  - Load
    - ...
  - ...
- Examples
  - look at the file titles in frontend/public/workflows/ and create markdowns
  - leave contents blank

Write the content introducing the software's principles, including the concept of Visual Programming, and the basic concepts of nodes, types in the project, flows, and uploading and downloading files.
Write the content of introducing All the Nodes, including what each options means and their format, what the node do, and what should be expected to be outputed.
If possible, try to make all places mention types colored, make the page colorful. Color should be utilized to convey information.

When completed, write a github pages script and a gitlab pages script, to host only the document on github and gitlab(not the frontend).