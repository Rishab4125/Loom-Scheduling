# Loom-Scheduling

## Overview

This repository provides an optimization-based scheduling solution for industrial job scheduling problems using the Gurobi Optimizer.

The original implementation was developed to solve the loom machine scheduling problem in the plastic woven sack manufacturing industry, where multiple jobs must be allocated across limited loom machines while respecting operational constraints.
However, the framework is generalizable to other manufacturing scheduling problems with minor adjustments to parameters and constraints.
The objective is to efficiently allocate jobs to machines to optimize production planning, reduce idle time, and improve operational efficiency.

## Problem Statement

- In manufacturing environments, machines must process multiple jobs with constraints such as:
- Limited number of machines
- Job processing times
- Machine availability
- Job priorities or deadlines
- Setup or changeover constraints
- Manually scheduling such operations is inefficient and often leads to suboptimal production plans.
- This project formulates the scheduling problem as a Mixed Integer Linear Programming (MILP) model and solves it using Gurobi.

## Technologies Used

- Python
- Gurobi Optimizer
- Operations Research / Optimization
- Industrial Scheduling
