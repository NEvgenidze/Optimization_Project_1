import gurobipy as gp
from gurobipy import GRB
import math

# Start building the optimization model
model = gp.Model("Child_Care_Desert_Expansion_and_Distance")

# Decision variables for new facilities (small, medium, large) in each zip code
new_facilities = {}
for zip_code in child_care_deserts:
    new_facilities[f"{zip_code}_small"] = model.addVar(vtype=GRB.BINARY, name=f"new_small_{zip_code}")
    new_facilities[f"{zip_code}_medium"] = model.addVar(vtype=GRB.BINARY, name=f"new_medium_{zip_code}")
    new_facilities[f"{zip_code}_large"] = model.addVar(vtype=GRB.BINARY, name=f"new_large_{zip_code}")

# Step 2: Define decision variables for expansion and auxiliary variables for piecewise cost
expansions = {}
piecewise_expansion = {}
for facility_id, info in child_care_capacity_data.items():
    expansions[facility_id] = model.addVar(vtype=GRB.CONTINUOUS, name=f"expansion_{facility_id}", lb=0, ub=0.2)  # Max 20% expansion
    
    # Define auxiliary variables for the three expansion ranges
    piecewise_expansion[facility_id] = {
        'x1': model.addVar(vtype=GRB.CONTINUOUS, name=f"expansion_x1_{facility_id}", lb=0, ub=0.1),  # 0-10%
        'x2': model.addVar(vtype=GRB.CONTINUOUS, name=f"expansion_x2_{facility_id}", lb=0, ub=0.05), # 10-15%
        'x3': model.addVar(vtype=GRB.CONTINUOUS, name=f"expansion_x3_{facility_id}", lb=0, ub=0.05)  # 15-20%
    }
    
    # Ensure that the total expansion is the sum of expansions in each piece
    model.addConstr(expansions[facility_id] == piecewise_expansion[facility_id]['x1'] + 
                    piecewise_expansion[facility_id]['x2'] + 
                    piecewise_expansion[facility_id]['x3'], name=f"expansion_split_{facility_id}")

# Step 3: Define expansion costs using the piecewise expansions
expansion_cost = {}
for facility_id, info in child_care_capacity_data.items():
    original_capacity = info  # Total capacity of the facility
    
    # Calculate the cost for each expansion range
    cost_x1 = 20000 + 200 * original_capacity * piecewise_expansion[facility_id]['x1']  # Up to 10%
    cost_x2 = 400 * original_capacity * piecewise_expansion[facility_id]['x2']          # 10-15%
    cost_x3 = 1000 * original_capacity * piecewise_expansion[facility_id]['x3']         # 15-20%
    
    # Total cost for expansion
    expansion_cost[facility_id] = cost_x1 + cost_x2 + cost_x3

# Objective: Minimize the total cost of building new facilities and expanding existing ones
total_cost = gp.quicksum(
    65000 * new_facilities[f"{zip_code}_small"] + 
    95000 * new_facilities[f"{zip_code}_medium"] + 
    115000 * new_facilities[f"{zip_code}_large"]
    for zip_code in child_care_deserts
)

# Add the cost of expansion based on the piecewise linear cost
total_cost += gp.quicksum(expansion_cost[facility_id] for facility_id in expansion_cost)

model.setObjective(total_cost, GRB.MINIMIZE)

# Add constraints to ensure enough slots are added to meet demand
for zip_code, desert_info in child_care_deserts.items():
    required_capacity = desert_info["difference_child_care_capacity"]
    required_0_5_capacity = desert_info["difference_0_5_capacity"]
    
    # Total new slots added (small, medium, large facilities)
    total_new_capacity = (100 * new_facilities[f"{zip_code}_small"] + 
                          200 * new_facilities[f"{zip_code}_medium"] + 
                          400 * new_facilities[f"{zip_code}_large"])
    
    # Total expansion capacity added
    total_expansion_capacity = gp.quicksum(
        expansions[facility_id] * child_care_capacity_data[facility_id]
        for facility_id in child_care_capacity_data if facility_id == zip_code
    )
    
    # Add constraint for total capacity (new + expansion) >= required capacity
    model.addConstr(total_new_capacity + total_expansion_capacity >= required_capacity, name=f"capacity_constraint_{zip_code}")

# Step 5: Distance constraint - Ensure no two facilities are within 0.06 miles of each other
def haversine(lat1, lon1, lat2, lon2):
    R = 3959.87433  # Radius of Earth in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c  # Distance in miles

# Assuming location_data contains latitude, longitude for zip codes
for i, (zip_code_i, lat_lon_i) in enumerate(location_data.items()):
    for j, (zip_code_j, lat_lon_j) in enumerate(location_data.items()):
        if i < j:  # Only check each pair once
            distance = haversine(lat_lon_i[0], lat_lon_i[1], lat_lon_j[0], lat_lon_j[1])
            if distance < 0.06:
                # Add constraint that at most one facility can be built/expanded if they're too close
                model.addConstr(
                    new_facilities[f"{zip_code_i}_small"] + 
                    new_facilities[f"{zip_code_i}_medium"] + 
                    new_facilities[f"{zip_code_i}_large"] +
                    new_facilities[f"{zip_code_j}_small"] + 
                    new_facilities[f"{zip_code_j}_medium"] + 
                    new_facilities[f"{zip_code_j}_large"] <= 1, 
                    name=f"distance_constraint_{zip_code_i}_{zip_code_j}"
                )

# Solve the model
model.optimize()

# Output the result
if model.status == GRB.OPTIMAL:
    print(f'Optimal objective value: {model.objVal}')
    for v in model.getVars():
        print(f'{v.varName}: {v.x}')
else:
    print("No optimal solution found")
