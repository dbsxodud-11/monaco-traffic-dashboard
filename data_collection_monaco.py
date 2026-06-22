import os
import copy
import csv
import pickle
import argparse
import subprocess
import xml.etree.ElementTree as ET

import random
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm

import traci
from sumolib import checkBinary
from sumolib.miscutils import getFreeSocketPort

import multiprocessing as mp
from collections import defaultdict

def get_default_routes(route_number, simulation_time, route_file):
    sumocfg_file = "sumo/Monaco/monaco.sumocfg"
    with open(sumocfg_file, "w") as f:
        f.write(f'<configuration>\n')
        f.write(f'    <input>\n')
        f.write(f'        <net-file value="default_dense.net.xml"/>\n')
        f.write(f'        <route-files value="default.rou.xml"/>\n')
        f.write(f'    </input>\n')
        f.write(f'    <time>\n')
        f.write(f'        <begin value="0"/>\n')
        f.write(f'        <end value="3600"/>\n')
        f.write(f'    </time>\n')
        f.write(f'</configuration>\n')

    sumo_cmd = ["sumo", "-c", sumocfg_file, "--tripinfo-output", "sumo/Monaco/mocano.tripinfo.xml"]
    port = getFreeSocketPort()
    
    traci.start(sumo_cmd)
    node_list = traci.junction.getIDList()
    edge_list = traci.edge.getIDList()

    routes = []
    for _ in range(route_number):
        start_edge = random.choice(edge_list)
        end_edge = random.choice(edge_list)
        routes.append((start_edge, end_edge, 325))

    if os.path.exists(route_file):
        print(f"File {route_file} already exists. Use existing file.")
    else:
        with open(f"{route_file}", 'w') as f:
            f.write(f'<routes>\n')
            for i, (start_edge, end_edge, num_vehicles) in enumerate(routes):
                f.write(f'    <flow id="{i}" begin="0" end="{simulation_time // 2}" from="{start_edge}" to="{end_edge}" vehsPerHour="{num_vehicles}" />\n')
            f.write('</routes>\n')
    traci.close()

def get_default_network(network_file):
    sumocfg_file = "sumo/Monaco/monaco.sumocfg"
    with open(sumocfg_file, "w") as f:
        f.write(f'<configuration>\n')
        f.write(f'    <input>\n')
        f.write(f'        <net-file value="default_dense.net.xml"/>\n')
        f.write(f'        <route-files value="default_dense.rou.xml"/>\n')
        f.write(f'    </input>\n')
        f.write(f'    <time>\n')
        f.write(f'        <begin value="0"/>\n')
        f.write(f'        <end value="3600"/>\n')
        f.write(f'    </time>\n')
        f.write(f'</configuration>\n')

    sumo_cmd = ["sumo", "-c", sumocfg_file, "--tripinfo-output", "sumo/Monaco/mocano.tripinfo.xml"]
    port = getFreeSocketPort()
    
    traci.start(sumo_cmd)
    traci.simulationStep()
    node_list = traci.junction.getIDList()
    edge_list = traci.edge.getIDList()

    if not os.path.exists("sumo/Monaco/eternal_edges.pkl"):
        eternal_edges = set()
        for vehicle in traci.vehicle.getIDList():
            if vehicle.endswith('.0'):
                routes = traci.vehicle.getRoute(vehicle)
                eternal_edges.update(routes)

        # eternal_edges = set()
        tree = ET.parse("sumo/Monaco/default_dense.rou.xml")
        root = tree.getroot()
        for child in root[1:]:
            eternal_edges.add(child.attrib['from'])
            eternal_edges.add(child.attrib['to'])
        eternal_edges = list(eternal_edges)
        with open("sumo/Monaco/eternal_edges.pkl", "wb") as f:
            pickle.dump(eternal_edges, f)
    else:
        with open("sumo/Monaco/eternal_edges.pkl", "rb") as f:
            eternal_edges = pickle.load(f)
    traci.close()
    
    possible_edges = copy.deepcopy(edge_list)
    # only keep edges with - sign
    possible_edges = [edge for edge in possible_edges if '-' in edge]

    # print(f"Number of edges: {len(possible_edges)}")
    # print(kyle)
    # mask eternal edges
    masks = []
    for edge in possible_edges:
        if edge in eternal_edges:
            masks.append(1)
        else:
            masks.append(0)
    masks = np.array(masks)

    return possible_edges, masks

def construct_network_file(network_file, remove_edges):
    remove_edges = ', '.join(remove_edges)
    subprocess.call(f'netconvert -s sumo/Monaco/default_dense.net.xml -o {network_file} --remove-edges.explicit="{remove_edges}"', shell=True)

def simulation(idx, args, possible_edges, masks, folder_name, seed):
    random.seed(seed+idx)
    np.random.seed(seed+idx)
    remove_ratio = np.random.uniform(0.05, 0.5)
    xs = np.random.choice(2, size=len(possible_edges), p=[1-remove_ratio, remove_ratio])
    xs[masks == 1] = 0
    remove_edges = [possible_edges[i] for i in range(len(xs)) if xs[i] == 1]

    sumocfg_file = "sumo/Monaco/monaco.sumocfg"
    with open(sumocfg_file, "w") as f:
        f.write(f'<configuration>\n')
        f.write(f'    <input>\n')
        f.write(f'        <net-file value="default_dense.net.xml"/>\n')
        f.write(f'        <route-files value="default_dense.rou.xml"/>\n')
        f.write(f'    </input>\n')
        f.write(f'    <time>\n')
        f.write(f'        <begin value="0"/>\n')
        f.write(f'        <end value="3600"/>\n')
        f.write(f'    </time>\n')
        f.write(f'</configuration>\n')

    sumo_cmd = ["sumo", "-c", sumocfg_file, "--tripinfo-output", "sumo/Monaco/mocano.tripinfo.xml"]
    port = getFreeSocketPort()
    
    traci.start(sumo_cmd)
    node_list = traci.junction.getIDList()
    edge_list = traci.edge.getIDList()

    G = nx.Graph()
    for node in node_list:
        G.add_node(node, pos=(traci.junction.getPosition(node)))
    for edge in edge_list:
        start_node = traci.edge.getFromJunction(edge)
        end_node = traci.edge.getToJunction(edge)
        G.add_edge(start_node, end_node)
    
    G_new = copy.deepcopy(G)
    for edge in remove_edges:
        start_node = traci.edge.getFromJunction(edge)
        end_node = traci.edge.getToJunction(edge)
        if G_new.has_edge(start_node, end_node):
            G_new.remove_edge(start_node, end_node)
         
    # Remove isolated edges
    # components = list(nx.connected_components(G_new))
    # largest_component = max(components, key=len)
    # G_new = G_new.subgraph(largest_component).copy()

    for _ in range(10):
        add_edges = []
        for node in G_new.nodes():
            neighbors = list(G_new.neighbors(node))
            if len(neighbors) <= 1:
                possible_candidates = list(G.neighbors(node))
                possible_candidates = list(set(possible_candidates) - set(G_new.neighbors(node)))
                possible_candidates = list(sorted(possible_candidates))
                if len(possible_candidates) > 0:
                    chosen_node = np.random.choice(possible_candidates)
                    add_edges.append((node, chosen_node))
                    for outgoing_edge in traci.junction.getOutgoingEdges(node):
                        if outgoing_edge in traci.junction.getIncomingEdges(chosen_node):
                            if outgoing_edge in remove_edges:
                                remove_edges.remove(outgoing_edge)
                            elif f"-{outgoing_edge}" in remove_edges:
                                remove_edges.remove(f"-{outgoing_edge}")
                            else:
                                continue
                            break
                    
        for edge in add_edges:
            G_new.add_edge(edge[0], edge[1])

    remove_edges_pair = []
    for edge in remove_edges:
        remove_edges_pair.append(edge[1:])
    remove_edges += remove_edges_pair

    # remove_edges = ', '.join(remove_edges)
    traci.close()
    # Construct network file
    new_network_file = f"{folder_name}/gen_{idx}.net.xml"
    construct_network_file(new_network_file, remove_edges)
    
    # Run simulation
    sumocfg_file = f"{folder_name}/gen_{idx}.sumocfg"
    tripinfo_file = f"{folder_name}/gen_{idx}.tripinfo.xml"
    with open(sumocfg_file, "w") as f:
        f.write(f'<configuration>\n')
        f.write(f'    <input>\n')
        f.write(f'        <net-file value="gen_{idx}.net.xml"/>\n')
        f.write(f'        <route-files value="default_dense.rou.xml"/>\n')
        f.write(f'    </input>\n')
        f.write(f'    <time>\n')
        f.write(f'        <begin value="0"/>\n')
        f.write(f'        <end value="{args.simulation_time}"/>\n')
        f.write(f'    </time>\n')
        f.write(f'</configuration>\n')
        
    if args.visualize:
        sumoBinary = checkBinary('sumo-gui')
    else:
        sumoBinary = checkBinary('sumo')
    sumo_cmd = [sumoBinary, "-c", sumocfg_file, "--no-warnings", "--no-step-log", "--seed", "42", "--tripinfo-output", tripinfo_file]
    port = getFreeSocketPort()
    
    try:
        traci.start(sumo_cmd, port=port)
        # while traci.simulation.getMinExpectedNumber() > 0:
        for _ in range(args.simulation_time):
            traci.simulationStep()
        traci.close()
        
        # Post-process
        waiting_time_list = []
        traveling_time_list = []
        last_vehicle_arrival_time = 0
        tree = ET.parse(tripinfo_file)
        root = tree.getroot()
        for child in root:
            waiting_time_list.append(float(child.attrib['waitingTime']))
            traveling_time_list.append(float(child.attrib['duration']))
            last_vehicle_arrival_time = max(last_vehicle_arrival_time, float(child.attrib['arrival']))
        y = np.array([np.mean(waiting_time_list), np.mean(traveling_time_list), last_vehicle_arrival_time])
        print(f"Average waiting time: {np.mean(waiting_time_list):.2f}", end="\t")
        print(f"Average traveling time: {np.mean(traveling_time_list):.2f}", end="\t")
        print(f"Last vehicle arrival time: {last_vehicle_arrival_time:.2f}")
    except Exception as e:
        traci.close()
        print(f"Error: {e}")
        return xs, np.array([-1, -1, -1])
    return xs, y

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Network parameters
    # parser.add_argument("--grid_number", type=int, default=12)
    # parser.add_argument("--grid_length", type=float, default=50.0)
    
    # Route parameters
    parser.add_argument("--route_number", type=int, default=20)
    # parser.add_argument("--route_type", type=str, default="random")
    # parser.add_argument("--min_num_vehicles", type=int, default=100)
    # parser.add_argument("--max_num_vehicles", type=int, default=200)
    
    # Simulation parameters
    parser.add_argument("--simulation_time", type=int, default=3600)
    
    # seed
    parser.add_argument("--seed", type=int, default=42)
    
    # visualize
    parser.add_argument("--visualize", action="store_true")
    
    # data collection
    parser.add_argument("--num_data_points", type=int, default=10)
    
    args = parser.parse_args()
    
    # Set seed
    seed = args.seed
    random.seed(seed)
    np.random.seed(seed)
    
    folder_name = f"sumo/Monaco"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name, exist_ok=True)

    # Get Default Routes
    # route_file = f"{folder_name}/default_dense.rou.xml"
    # get_default_routes(args.route_number, args.simulation_time, route_file=route_file)

    # Get Default Network
    network_file = f"{folder_name}/default_dense.net.xml"
    possible_edges, masks = get_default_network(network_file)
    
    inputs = [(i, args, possible_edges, masks, folder_name, seed) for i in range(args.num_data_points)]
    with mp.Pool(4) as pool:
        data = pool.starmap(simulation, tqdm(inputs, total=args.num_data_points))
        
    # Save data
    X = np.stack([d[0] for d in data])
    y = np.stack([d[1] for d in data])
    # np.savez_compressed("data/random.npz", X=X, y=y)
    save_path = f"results/Monaco/data/preprocessed"
    if not os.path.exists(save_path):
        os.makedirs(save_path, exist_ok=True)
    npz_save_path = os.path.join(save_path, f"data_{args.num_data_points}.npz")
    np.savez_compressed(npz_save_path, X=X, y=y)
    
    csv_save_path = os.path.join(save_path, f"sumo_preprocessed_dataset_iter1.csv")
    csv_data = []
    data = np.load(npz_save_path)
    
    data_x = data["X"]
    data_y = data["y"] 
    
    for x, y in zip(data_x, data_y):
        layout = "".join(map(str, x))
        waiting_time = y[0]  # y의 첫 번째 값
        csv_data.append([layout, waiting_time])
    
    with open(csv_save_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow(["layout", "waiting_time"])
        writer.writerows(csv_data)