import os
import json
file_path = "backend/data/simulation_results.json"
if os.path.exists(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Simulations:", data.get("num_simulations"))
    print("Last updated:", data.get("last_updated"))
    
    group_c_probs = [p for p in data.get("probabilities", []) if p.get("group_name") == "C"]
    print("\n--- Simulation Probabilities for Group C ---")
    for p in group_c_probs:
        print(f"Team: {p['team']}, Exit%: {p['group_exit_pct']}, Champ%: {p['champion_pct']}")
else:
    print("Simulation results file does not exist!")
