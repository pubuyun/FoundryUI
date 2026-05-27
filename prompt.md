1. Do not select hydrogen atoms if user clicked select all in a selector.
2. Add the names of the sidebar under the icon, like LOGS, SAVE...
3. Now Scrolling NODES and LOGS sidebar will scroll the whole page, make it only scroll the sidebar content.
4. make the nodes in NODES sidebar have different color based on their output color.
5. Make the downloadable ARCHIVED and ERROR more visible, by adding a colored background to them and set text color to white, just like RUNNING and STOPPED.
6. If the run is stopped, also make its archive available, just like error or archived.
7. Do not change the position of nodes editor when sidebar pops up or hides. Implement this by first moving the baklavajs components(Copy, paste, revert...) to the right, and make left side bar at the top layer, only overlapping the node editor, do not mawke them in the same flexbox or container.
8. Add a text replacing the default "Text Field" to indicate that manual nodes cannot be preselected, but need to select manually when the run flows there. Replace all Manual nodes' defualt placehoders(For Filter by score, in field selector).
