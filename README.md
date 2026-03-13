# Loom-Scheduling

## Overview

This repository provides an optimization-based scheduling solution for industrial job scheduling problems using the Gurobi Optimizer.

The original implementation was developed to solve the loom machine scheduling problem in the plastic woven sack manufacturing industry, where multiple jobs must be allocated across limited loom machines while respecting operational constraints.
However, the framework is generalizable to other manufacturing scheduling problems with minor adjustments to parameters and constraints.
The objective is to efficiently allocate jobs to machines to optimize production planning, reduce idle time, and improve operational efficiency.

## Problem Statement

In manufacturing environments, machines must process multiple jobs with constraints such as:
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

# Industry Overview: Plastic Woven Sack Manufacturing

The plastic woven sack industry is a significant segment of the global packaging sector, primarily serving industries such as agriculture, cement, chemicals, fertilizers, food grains, and polymers. These sacks are valued for their high tensile strength, durability, moisture resistance, and cost efficiency, making them suitable for bulk packaging and transportation.

Plastic woven sacks are typically manufactured from polypropylene (PP) or high-density polyethylene (HDPE). The production process involves transforming polymer granules into woven fabric through a series of mechanical and thermal processes, followed by fabrication into sacks of specific sizes and specifications.

The industry operates in a high-volume production environment, where multiple machines operate simultaneously and production planning plays a crucial role in ensuring efficient utilization of resources. Since customer orders often vary in size, weight capacity, printing requirements, and delivery timelines, manufacturers face complex scheduling challenges across different stages of the production process.

## Manufacturing Process Stages

The production of plastic woven sacks generally involves the following stages:
- Extrusion and Tape Production
Polypropylene or HDPE granules are melted and extruded into thin plastic films, which are then slit into narrow tapes and stretched to improve tensile strength.
- Tape Winding
The stretched tapes are wound onto bobbins to prepare them for the weaving stage.
- Weaving (Loom Operation)
Circular or flat loom machines interlace the tapes to produce woven fabric rolls. This stage is one of the most critical and resource-intensive steps in the manufacturing process.
- Lamination (Optional)
For applications requiring moisture resistance or improved durability, the woven fabric may be laminated with a thin plastic film.
- Printing
The woven fabric or finished sacks may undergo printing to include branding, product information, or regulatory labels.
- Cutting and Stitching
Fabric rolls are cut into specific lengths and stitched to form sacks according to required dimensions.
- Quality Inspection and Packaging
Finished sacks are inspected for defects and packaged for shipment.

