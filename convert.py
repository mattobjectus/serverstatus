import json


file_path = './test/demo/DeviceTypes.json'

with open(file_path, 'r') as file:
    data_dict = json.load(file)

for device_info in data_dict:
    print(f'|{device_info["VendorIcon"]}|{device_info["MachineType"]}|{device_info["Total"]}|')