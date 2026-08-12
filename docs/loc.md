\# Lines of Code (LOC)



\## 1. Overview



Lines of Code (LOC) is a source-code size metric used to measure the physical size of Python source files.



In CodeInsight, LOC is calculated using the `radon.raw.analyze` function.



The engine uses Radon's raw source-code analysis rather than implementing a custom LOC counting algorithm.



In addition to LOC, the engine stores several related raw source-code metrics provided by Radon.



\---



\## 2. Purpose



LOC is used to measure the size of the analyzed Python codebase.



LOC provides useful contextual information for interpreting other software metrics, including:



\- Cyclomatic Complexity

\- Cognitive Complexity

\- Halstead Volume

\- Code Smells

\- Code Churn

\- Duplication



LOC alone does not determine code quality. A larger codebase is not necessarily a lower-quality codebase.



\---



\## 3. Analysis Scope



The metric is calculated for all Python source files provided to the engine.



Each file is analyzed independently using Radon.



For multiple files, the engine aggregates the results:



```text

Total LOC = LOC(file1) + LOC(file2) + ... + LOC(fileN)

