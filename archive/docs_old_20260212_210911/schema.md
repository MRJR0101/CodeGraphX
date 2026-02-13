# Graph Schema (MVP)

## Nodes
| Node     | Purpose                          |
|----------|----------------------------------|
| Project  | One repo/system                  |
| File     | Physical file                    |
| Module   | Logical module (Python packages) |
| Class    | Class definitions                |
| Function | Functions & methods              |
| Symbol   | Variables, constants, globals    |

## Edges
| Edge      | Meaning                         |
|-----------|---------------------------------|
| CONTAINS  | Project → File → Class/Function |
| IMPORTS   | File/Module depends on another  |
| DEFINES   | File defines symbol             |
| CALLS     | Function invokes function       |
| READS     | Function reads variable         |
| WRITES    | Function mutates variable       |
| INHERITS  | Class extends class             |
| OVERRIDES | Method overrides parent         |
| RETURNS   | Function returns type/symbol    |
