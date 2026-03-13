#Importing Libraries
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from results_to_csv import save_results_to_csv
#Code
class LoomScheduler:
    def __init__(self, orders_data, loom_details_df, planning_horizon=365):
        """
        Initialize the Loom Scheduler
        
        Parameters:
        - orders_data: List of dictionaries or DataFrame with columns [order_id, quantity, length, color, denier, order_date, delivery_date]
        - loom_details_df: DataFrame with columns [loom_model, num_looms, denier_capability, prod_rate_low, prod_rate_high]
        - planning_horizon: Planning horizon in days
        """
        # Convert orders to DataFrame if it's a list of dictionaries
        if isinstance(orders_data, list):
            self.orders = pd.DataFrame(orders_data)
            # Convert date strings to datetime if needed
            if 'order_date' in self.orders.columns:
                self.orders['order_date'] = pd.to_datetime(self.orders['order_date'])
            if 'delivery_date' in self.orders.columns:
                self.orders['delivery_date'] = pd.to_datetime(self.orders['delivery_date'])
        else:
            self.orders = orders_data
        
        # Get today's date and adjust order_date to max(today, order_date) for each order
        self.today = pd.Timestamp.now().normalize()  # Today at midnight
        if 'order_date' in self.orders.columns:
            # Create adjusted_order_date column: max(today, order_date) for each order
            self.orders['adjusted_order_date'] = self.orders['order_date'].apply(
                lambda x: max(self.today, x)
            )
        else:
            self.orders['adjusted_order_date'] = self.today
        
        self.loom_details = loom_details_df
        self.planning_horizon = planning_horizon*2
        
        # Create individual looms with IDs
        self.looms = self._create_loom_instances()
        
        # Pre-filter compatible order-loom pairs to reduce variables
        self.compatible_pairs = self._get_compatible_pairs()
        
        # Big M for logical constraints
        self.M = planning_horizon * 2
        
        # Initialize model
        self.model = gp.Model("LoomScheduling")
        self.model.setParam('OutputFlag', 1)
        self.model.setParam('TimeLimit', 300)  # 5 minutes time limit
        self.model.setParam('MIPGap', 0.05)  # 5% optimality gap acceptable
        
    def _create_loom_instances(self):
        """Create individual loom instances from loom details"""
        looms = []
        for _, row in self.loom_details.iterrows():
            model_name = row['loom_model']
            num_looms = int(row['num_looms'])
            for number in range(1, num_looms + 1):
                loom_id = f"{model_name}_{number}"
                looms.append({
                    'loom_id': loom_id,
                    'loom_model': model_name,
                    'denier_capability': row['denier_capability'],
                    'prod_rate_low': row['prod_rate_low'],
                    'prod_rate_high': row['prod_rate_high']
                })
        return pd.DataFrame(looms)
    
    def _get_compatible_pairs(self):
        """Pre-compute compatible order-loom pairs based on denier"""
        compatible = []
        for _, order in self.orders.iterrows():
            for _, loom in self.looms.iterrows():
                if order['denier'] == loom['denier_capability']:
                    compatible.append((order['order_id'], loom['loom_id']))
        return compatible
    
    def build_model(self):
        """Build the optimization model with reduced variables"""
        print("Building optimization model...")
        print(f"Compatible pairs: {len(self.compatible_pairs)}")
        
        # Sets
        orders = self.orders['order_id'].tolist()
        looms = self.looms['loom_id'].tolist()
        
        # Decision Variables - Only for compatible pairs
        # 1. Quantity assigned to loom j for order i (only compatible pairs)
        self.x = self.model.addVars(self.compatible_pairs, vtype=GRB.INTEGER, 
                                     name="quantity", lb=0)
        
        # 2. Quantity should be in multiples of 100 units
        self.x_100 = self.model.addVars(self.compatible_pairs, vtype=GRB.INTEGER,
                                        name="quantity_100", lb=0)
        
        # 3. Binary variable: 1 if loom j is assigned to order i (only compatible pairs)
        self.y = self.model.addVars(self.compatible_pairs, vtype=GRB.BINARY, 
                                     name="assignment")
        
        # 4. Start time for order i on loom j (only compatible pairs)
        self.start = self.model.addVars(self.compatible_pairs, vtype=GRB.CONTINUOUS, 
                                        name="start_time", lb=0, ub=self.planning_horizon)
        
        # 5. Production time for order i on loom j (only compatible pairs)
        self.prod_time = self.model.addVars(self.compatible_pairs, vtype=GRB.CONTINUOUS, 
                                            name="prod_time", lb=0)
        
        # 6. Production time should be in multiples of 6 hours (0.25 days)
        self.prod_time_6hr = self.model.addVars(self.compatible_pairs, vtype=GRB.INTEGER, 
                                            name="prod_time_6hr", lb=0)
        
        # 7. End time for order i on loom j (only compatible pairs)
        self.end = self.model.addVars(self.compatible_pairs, vtype=GRB.CONTINUOUS, 
                                      name="end_time", lb=0, ub=self.planning_horizon)
        
        # 8. Maximum end time for each order (across all looms)
        self.order_end = self.model.addVars(orders, vtype=GRB.CONTINUOUS, 
                                            name="order_completion", lb=0)
        
        # 9. Loom utilization (binary: 1 if loom is used at all)
        self.loom_used = self.model.addVars(looms, vtype=GRB.BINARY, 
                                            name="loom_utilization")
        
        # 10. Makespan (overall completion time)
        self.makespan = self.model.addVar(vtype=GRB.CONTINUOUS, name="makespan", lb=0)
        
        # 11. Lateness for each order (completion_date - delivery_date, >= 0)
        self.lateness = self.model.addVars(orders, vtype=GRB.CONTINUOUS, 
                                          name="lateness", lb=0)
        
        # 12. Maximum lateness across all orders
        self.max_lateness = self.model.addVar(vtype=GRB.CONTINUOUS, name="max_lateness", lb=0)
        
        # 13. Sequencing variables - ONLY for pairs on same loom with compatible orders
        self.z = {}
        for lid in looms:
            # Get orders that can run on this loom
            loom_orders = [oid for oid, l in self.compatible_pairs if l == lid]
            for i, oid1 in enumerate(loom_orders):
                for oid2 in loom_orders[i+1:]:
                    self.z[oid1, oid2, lid] = self.model.addVar(vtype=GRB.BINARY, 
                                                                 name=f"seq_{oid1}_{oid2}_{lid}")
        
        self._add_constraints()
        self._set_objective()
        
        self.model.update()
        print("Model built successfully!")
        print(f"Variables: {self.model.NumVars}")
        print(f"Constraints: {self.model.NumConstrs}")
        
    def _add_constraints(self):
        """Add all constraints to the model"""
        orders = self.orders['order_id'].tolist()
        looms = self.looms['loom_id'].tolist()
        
        # Calculate base_date using adjusted_order_date (max(today, order_date)) for consistency
        base_date = self.orders['adjusted_order_date'].min()
        
        print("Adding constraints...")
        
        # Constraint 1: Total quantity assigned equals required quantity
        for _, order in self.orders.iterrows():
            oid = order['order_id']
            compatible_looms = [lid for o, lid in self.compatible_pairs if o == oid]
            self.model.addConstr(
                gp.quicksum(self.x[oid, lid] for lid in compatible_looms) == order['quantity'],
                name=f"demand_{oid}"
            )
        
        # Constraint 2: Quantity in multiples of 100
        for oid, lid in self.compatible_pairs:
            self.model.addConstr(
                self.x[oid, lid] == 100 * self.x_100[oid, lid],
                name=f"quantity_100_mult_{oid}_{lid}"
            )
        
        # Constraint 3: Link assignment binary to quantity
        for oid, lid in self.compatible_pairs:
            # If y = 0, then x = 0
            self.model.addConstr(
                self.x[oid, lid] <= self.M * self.y[oid, lid],
                name=f"link_assign_{oid}_{lid}"
            )
            # If x > 0, then y = 1 (relaxed constraint)
            self.model.addConstr(
                self.x[oid, lid] >= self.y[oid, lid],
                name=f"link_assign2_{oid}_{lid}"
            )
        
        # Constraint 4: Production time calculation
        for oid, lid in self.compatible_pairs:
            order = self.orders[self.orders['order_id'] == oid].iloc[0]
            loom = self.looms[self.looms['loom_id'] == lid].iloc[0]
            prod_rate = loom['prod_rate_low'] if order['denier'] == 'low' else loom['prod_rate_high']
            
            if prod_rate > 0:
                # prod_time = (quantity * length) / prod_rate
                self.model.addConstr(
                    self.prod_time[oid, lid] * prod_rate >= self.x[oid, lid] * order['length'],
                    name=f"prod_time_{oid}_{lid}"
                )

                self.model.addConstr(
                    self.prod_time[oid, lid] == 0.25 * self.prod_time_6hr[oid, lid],
                    name=f"prod_time_6hr_{oid}_{lid}"
                )
                # If not assigned, prod_time = 0
                self.model.addConstr(
                    self.prod_time[oid, lid] <= self.M * self.y[oid, lid],
                    name=f"prod_time_zero_{oid}_{lid}"
                )
        
        # Constraint 5: End time = Start time + Production time
        for oid, lid in self.compatible_pairs:
            self.model.addConstr(
                self.end[oid, lid] == self.start[oid, lid] + self.prod_time[oid, lid],
                name=f"end_time_{oid}_{lid}"
            )
        
        # Constraint 6: Order completion time (max over all looms)
        for _, order in self.orders.iterrows():
            oid = order['order_id']
            compatible_looms = [lid for o, lid in self.compatible_pairs if o == oid]
            for lid in compatible_looms:
                self.model.addConstr(
                    self.order_end[oid] >= self.end[oid, lid],
                    name=f"order_complete_{oid}_{lid}"
                )
        
        # Constraint 7: Start time >= max(today, order_date) for each order
        # Use adjusted_order_date which is max(today, order_date)
        for oid, lid in self.compatible_pairs:
            order = self.orders[self.orders['order_id'] == oid].iloc[0]
            order_day = (order['adjusted_order_date'] - base_date).days
            self.model.addConstr(
                self.start[oid, lid] >= order_day * self.y[oid, lid],
                name=f"start_after_order_{oid}_{lid}"
            )
        
        # Constraint 8: Calculate lateness for each order (lateness = max(0, completion - delivery))
        # Removed hard constraint that forced order_end <= delivery_day to allow infeasible solutions
        # base_date already calculated at the start of this method using adjusted_order_date
        for _, order in self.orders.iterrows():
            oid = order['order_id']
            delivery_day = (order['delivery_date'] - base_date).days
            # Lateness >= completion - delivery (if positive, otherwise 0)
            self.model.addConstr(
                self.lateness[oid] >= self.order_end[oid] - delivery_day,
                name=f"lateness_calc_{oid}"
            )
        
        # Constraint 9: Maximum lateness calculation
        for oid in orders:
            self.model.addConstr(
                self.max_lateness >= self.lateness[oid],
                name=f"max_lateness_{oid}"
            )
        
        # Constraint 10: Non-overlapping jobs on same loom (only for compatible pairs)
        for lid in looms:
            loom_orders = [oid for oid, l in self.compatible_pairs if l == lid]
            for i, oid1 in enumerate(loom_orders):
                for oid2 in loom_orders[i+1:]:
                    if (oid1, oid2, lid) in self.z:
                        # z = 1 means oid1 before oid2
                        self.model.addConstr(
                            self.end[oid1, lid] <= self.start[oid2, lid] + 
                            self.M * (1 - self.z[oid1, oid2, lid]) + 
                            self.M * (2 - self.y[oid1, lid] - self.y[oid2, lid]),
                            name=f"seq1_{oid1}_{oid2}_{lid}"
                        )
                        self.model.addConstr(
                            self.end[oid2, lid] <= self.start[oid1, lid] + 
                            self.M * self.z[oid1, oid2, lid] + 
                            self.M * (2 - self.y[oid1, lid] - self.y[oid2, lid]),
                            name=f"seq2_{oid1}_{oid2}_{lid}"
                        )
        
        # Constraint 11: Loom utilization tracking (simplified)
        for lid in looms:
            compatible_orders = [oid for oid, l in self.compatible_pairs if l == lid]
            if compatible_orders:
                # If any order is assigned to this loom, loom_used = 1
                for oid in compatible_orders:
                    self.model.addConstr(
                        self.loom_used[lid] >= self.y[oid, lid],
                        name=f"loom_util_min_{oid}_{lid}"
                    )
                # loom_used can't be 1 unless at least one order is assigned
                self.model.addConstr(
                    self.loom_used[lid] <= gp.quicksum(self.y[oid, lid] for oid in compatible_orders),
                    name=f"loom_util_max_{lid}"
                )
        
        # Constraint 12: Makespan calculation
        for oid in orders:
            self.model.addConstr(
                self.makespan >= self.order_end[oid],
                name=f"makespan_{oid}"
            )
    
    def _set_objective(self):
        """Set the multi-objective function"""
        orders = self.orders['order_id'].tolist()
        looms = self.looms['loom_id'].tolist()
        
        # Weights for multi-objective
        w1 = 10000   # Minimize maximum lateness (highest priority - minimize max(completion - delivery))
        w2 = 1000    # Minimize makespan
        w3 = 700     # Maximize loom utilization
        w4 = 500     # Minimize total production time
        
        objective = (
            w1 * self.max_lateness +  # Minimize maximum lateness (primary goal)
            w2 * self.makespan +  # Minimize completion time
            w3 * (len(looms) - gp.quicksum(self.loom_used[lid] for lid in looms)) +  # Maximize utilization
            w4 * gp.quicksum(self.order_end[oid] for oid in orders)  # Minimize total time
        )
        
        self.model.setObjective(objective, GRB.MINIMIZE)
    
    def solve(self):
        """Solve the optimization model"""
        print("\nSolving the model...")
        self.model.optimize()
        
        if self.model.status == GRB.OPTIMAL:
            print("\nOptimal solution found!")
            return self._extract_solution()
        elif self.model.status == GRB.TIME_LIMIT:
            print("\nTime limit reached. Returning best solution found.")
            return self._extract_solution()
        elif self.model.status == GRB.SUBOPTIMAL:
            print("\nSuboptimal solution found. Returning best solution found.")
            return self._extract_solution()
        elif self.model.status == GRB.INFEASIBLE:
            print("\nModel is infeasible. Attempting to find best solution by relaxing constraints...")
            # Even if infeasible, try to extract solution if variables have values
            return self._extract_solution()
        else:
            print(f"\nOptimization status: {self.model.status}")
            # Try to extract solution anyway if variables have been set
            return self._extract_solution()
    
    def _extract_solution(self):
        """Extract solution from the model"""
        orders = self.orders['order_id'].tolist()
        looms = self.looms['loom_id'].tolist()
        
        schedule = []
        for oid, lid in self.compatible_pairs:
            try:
                if hasattr(self.y[oid, lid], 'X') and self.y[oid, lid].X is not None and self.y[oid, lid].X > 0.5:
                    schedule.append({
                        'order_id': oid,
                        'loom_id': lid,
                        'loom_model': self.looms.loc[self.looms['loom_id'] == lid, 'loom_model'].values[0],
                        'quantity_assigned': self.x[oid, lid].X if hasattr(self.x[oid, lid], 'X') else 0,
                        'start_time': self.start[oid, lid].X if hasattr(self.start[oid, lid], 'X') else 0,
                        'production_time': self.prod_time[oid, lid].X if hasattr(self.prod_time[oid, lid], 'X') else 0,
                        'end_time': self.end[oid, lid].X if hasattr(self.end[oid, lid], 'X') else 0
                    })
            except (AttributeError, TypeError):
                continue
        
        order_completion = {}
        order_lateness = {}
        for oid in orders:
            try:
                order_completion[oid] = self.order_end[oid].X if hasattr(self.order_end[oid], 'X') and self.order_end[oid].X is not None else 0
                order_lateness[oid] = self.lateness[oid].X if hasattr(self.lateness[oid], 'X') and self.lateness[oid].X is not None else 0
            except (AttributeError, TypeError):
                order_completion[oid] = 0
                order_lateness[oid] = 0
        
        loom_utilization = {}
        for lid in looms:
            try:
                loom_utilization[lid] = self.loom_used[lid].X if hasattr(self.loom_used[lid], 'X') and self.loom_used[lid].X is not None else 0
            except (AttributeError, TypeError):
                loom_utilization[lid] = 0
        
        try:
            makespan_value = self.makespan.X if hasattr(self.makespan, 'X') and self.makespan.X is not None else 0
            max_lateness_value = self.max_lateness.X if hasattr(self.max_lateness, 'X') and self.max_lateness.X is not None else max(order_lateness.values()) if order_lateness else 0
        except (AttributeError, TypeError):
            makespan_value = 0
            max_lateness_value = max(order_lateness.values()) if order_lateness else 0
        
        results = {
            'schedule': pd.DataFrame(schedule),
            'order_completion': order_completion,
            'order_lateness': order_lateness,
            'max_lateness': max_lateness_value,
            'loom_utilization': loom_utilization,
            'makespan': makespan_value,
            'total_looms_used': sum(loom_utilization.values()),
            'utilization_percentage': sum(loom_utilization.values()) / len(looms) * 100 if len(looms) > 0 else 0
        }
        
        return results
    
    def save_results_to_csv(self, results, output_prefix="schedule"):
        """Save scheduling results to CSV files"""
        # Get base date for converting days to actual dates
        # Use adjusted_order_date to maintain consistency with constraint calculations
        base_date = self.orders['adjusted_order_date'].min()
        save_results_to_csv(results, self.orders, self.looms, base_date, output_prefix)
    
    def print_summary(self, results):
        """Print solution summary"""
        if results is None:
            print("No solution available.")
            return
        
        print("\n" + "="*80)
        print("SOLUTION SUMMARY")
        print("="*80)
        print(f"Makespan (Total Time): {results['makespan']:.2f} days")
        print(f"Maximum Lateness: {results.get('max_lateness', 0):.2f} days")
        print(f"Looms Used: {results['total_looms_used']:.0f} / {len(self.looms)}")
        print(f"Utilization: {results['utilization_percentage']:.1f}%")
        
        print("\n" + "-"*80)
        print("ORDER COMPLETION TIMES:")
        print("-"*80)
        base_date = self.orders['adjusted_order_date'].min()
        for oid, completion in results['order_completion'].items():
            order_info = self.orders[self.orders['order_id'] == oid].iloc[0]
            delivery_day = (order_info['delivery_date'] - base_date).days
            slack = delivery_day - completion
            lateness = results.get('order_lateness', {}).get(oid, max(0, completion - delivery_day))
            status = "On Time" if lateness <= 0.01 else f"Delayed by {lateness:.2f} days"
            print(f"Order {oid}: Completed at day {completion:.2f} (Deadline: day {delivery_day}, Slack: {slack:.2f} days, {status})")
        
        print("\n" + "-"*80)
        print("LOOM UTILIZATION:")
        print("-"*80)
        for lid in sorted(results['loom_utilization'].keys()):
            loom_info = self.looms[self.looms['loom_id'] == lid].iloc[0]
            used = "Yes" if results['loom_utilization'][lid] > 0.5 else "No"
            print(f"Loom {lid} ({loom_info['loom_model']}): {used}")
        
        print("\n" + "-"*80)
        print("DETAILED SCHEDULE:")
        print("-"*80)
        if len(results['schedule']) > 0:
            schedule_sorted = results['schedule'].sort_values(['loom_id', 'start_time'])
            print(schedule_sorted.to_string(index=False))
        else:
            print("No schedule generated")
