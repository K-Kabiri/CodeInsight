\# Cognitive Complexity



\## 1. Overview



Cognitive Complexity is a software metric designed to estimate how difficult a piece of code is to understand and maintain from a human reader's perspective.



Unlike Cyclomatic Complexity, which primarily measures the number of independent execution paths, Cognitive Complexity focuses on the amount of mental effort required to understand the control flow of a program.



The metric was introduced by SonarSource as a way to measure the understandability of code.



In CodeInsight, Cognitive Complexity is calculated independently for each Python function or method and then aggregated at file and project level.



\---



\## 2. Purpose



The main purpose of Cognitive Complexity is to identify code that may be difficult for developers to understand.



A higher Cognitive Complexity generally indicates:



\- More complicated control flow

\- Deeper nesting

\- More branches

\- More interruptions in linear code flow

\- Increased mental effort required to understand the code



The metric can therefore be used as an indicator of maintainability and readability.



\---



\## 3. Calculation Model



The implementation follows the main principles of the Cognitive Complexity model introduced by SonarSource.



The metric is based on three major concepts:



1\. Structural increments

2\. Nesting increments

3\. Fundamental increments



Logical operator sequences are also considered according to the Cognitive Complexity model.



\---



\## 4. Structural Increments



Structural increments are added when the control flow of a function becomes more difficult to follow.



The following Python constructs are considered structural increments in CodeInsight:



\- `if`

\- `elif`

\- `else`

\- `for`

\- `while`

\- `except`

\- `match`

\- Conditional expressions (ternary expressions)



A structural increment is calculated as:



```text

increment = 1 + current\_nesting\_level

