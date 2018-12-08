import socket
import pickle
import sys

def isDigit(x):
  try:
    float(x)
    return True
  except (ValueError, TypeError) as e:
    return False

def buildKeyList(dict):
  key_list = []

  for key in sorted(rtt_params.keys()):
    #print('{0}:V:{1}'.format(key, rtt_params[key]))
    value = rtt_params[key]
    # If our value is a list of length one then turn it into a single value for easier editing
    if not isDigit(value):
      if len(value) == 1:
        value = value[0]
        key_list.append('{0}:L1:{1}'.format(key, value))
      else:
        #l_val = 'L' + str(len(value))
        key_list.append('{0}:L2:{1}'.format(key, value))
    else:
      # Just a single value
      if value >= 1.0:
        key_list.append('{0}:V:{1:.1f}'.format(key, value))
      elif value >= .01:
        key_list.append('{0}:V:{1:.3f}'.format(key, value))
      else:
        key_list.append('{0}:V:{1:.6f}'.format(key, value))

  return key_list



rt_tuning_file = '/data/.openpilot_rtt_params.pkl'

with open(rt_tuning_file, "rb") as f_read:
  rtt_params = pickle.load(f_read)

bind_ip = '0.0.0.0'
bind_port = 8777

while True:

  # Trying this inside the first loop
  server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  server.bind((bind_ip, bind_port))
  server.listen(5)  # max backlog of connections

  print 'Listening on {}:{}'.format(bind_ip, bind_port)

  c, addr = server.accept()
  print("Accepting connection")

  invalid_count = 0

  while invalid_count < 2:

    data = c.recv(1024)
    data = data.replace("\r\n", '') #remove new line character
    if len(data) > 3:
      invalid_count = 0
    else:
      invalid_count += 1
    inputStr = "Received " + data + " from " + addr[0]
    print inputStr
    if 'sendData' in data:
      key_list = buildKeyList(rtt_params)
      for str in key_list:
        c.send(str + '!')
    else:
      # We have an actual param:type:value coming in!!!
      # Match the param name up with the entry in our dictionary
      data_list = data.split(":")
      # Skip processing if there aren't 3 entries in data
      if len(data_list) != 3:
        continue
      # Set name and value
      data_name = data_list[0]
      data_type = data_list[1]
      data_value = data_list[2]
      old_value = rtt_params.get(data_name)
      if old_value:
        # Check to see if old value is a list
        if data_type == 'V':
          # Single value goes straight in
          try:
            rtt_params[data_name] = float(data_value)
          except:
            print('Could not convert received data_value into float.  Ignored.')
            print('data_value:  {0}'.format(data_value))
            continue
        elif data_type == 'L1':
          # List of length one was converted into single value.  Convert back.
          try:
            rtt_params[data_name] = [float(data_value)]
          except:
            print('Could not convert received L1 data_value into float.  Ignored.')
            print('data_value:  {0}'.format(data_value))
            continue
        elif data_type == 'L2':
          # List of length >2
          data_value = data_value.replace('[','').replace(']','')
          processed_entry = [float(s) for s in data_value.split(',') if isDigit(s)]
          if len(processed_entry) == 0:
            print('Invalid list entry.  Ignored.')
            continue
          if len(processed_entry) != len(old_value):
            print('New list length does not match length of original list.  Ignored.')
            continue    
          rtt_params[data_name] = processed_entry
        # If we made it to here then we have an updated entry in our rtt_params list.  Write it out to the file!
        with open(rt_tuning_file, "wb") as f_write:
          pickle.dump(rtt_params, f_write, -1)    # Dump to file with highest protocol (fastest)
        print('Successfully wrote updated rtt_params to real-time tuning file.')

    #c.send("Hello from Raspberry Pi!\nYou sent: " + data + "\nfrom: " + addr[0] + "\n")

    #if data == "Quit": break

  print("** Connection lost - Resetting connection **")

#c.send("Server stopped\n")
print "Server stopped"
c.close()

