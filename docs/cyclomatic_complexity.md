\# Cyclomatic Complexity



\## 1. Overview



Cyclomatic Complexity is a software metric used to measure the number of independent control-flow paths through a program.



In CodeInsight, Cyclomatic Complexity is calculated using Radon's `cc\_visit` implementation.



The metric is calculated at the block level, allowing CodeInsight to report complexity separately for functions, methods, and classes.



The implementation also stores the Radon complexity rank for each analyzed block.



\---



\## 2. Purpose



Cyclomatic Complexity is primarily used to measure the structural complexity of program control flow.



Higher Cyclomatic Complexity generally indicates that a block contains more decision points and therefore has more possible execution paths.



The metric can be used to identify code that may be:



\- harder to understand

\- harder to test

\- harder to maintain

\- more difficult to modify safely



Cyclomatic Complexity should not be interpreted as a complete measure of software quality by itself.



It is analyzed together with other CodeInsight metrics such as:



\- LOC

\- Cognitive Complexity

\- Halstead Volume

\- Coupling

\- Cohesion

\- Code Smells

\- Code Churn



\---



\## 3. Standard Definition



Cyclomatic Complexity was introduced by Thomas J. McCabe as a measure of the number of linearly independent paths through a program's control-flow graph.



For a connected control-flow graph, the classical definition is:



```text

M = E - N + 2

M = Cyclomatic Complexity
E = number of edges
N = number of nodes
