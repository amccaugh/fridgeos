#!/bin/bash

# created by Ryan Morgenstern @ NIST
# modify on 09/04/2024

# Script must be ran as sudo
if [ "$(id -u)" -ne 0 ]
  then echo Please run this script as root or using sudo!
  exit
fi

# Changing directory to your working directory
file_dir="/etc/udev/rules.d"
cd $file_dir #|| {echo "cd failed, edit \"file_dir\" in the script to find where your rules are located"; exit 1}
# Rule file to change or append to for persistant USB
file="69-serial.rules" 
# Rules line input format
#"SUBSYSTEM=="tty", ATTRS{serial}=="DF611CF78F804130", SYMLINK+="lockin-condenser",MODE = "0666"" >> /etc/udev/rules.d/99-serial.rules
# List of sensors to look for in rules file or to be added
sensor_list=("diodes" "heaters" "lockin" "warmup heaters")
search_time=30
add_rules_bool=True
user_rule_name_input=""

echo ""
echo Welcome to the persistant usb script
echo ""
echo This script will automattically update the "$file" file "(or start it)" and asign a global name to a device serial ID
echo ""
echo Please wait more than $search_time seconds between connecting different sensor microcontrollers
echo ""
echo This script reads dmesg and filters it out by the last $search_time seconds.
echo ""
#Check if a serial rule file exists
file_exists_bool="0"
for eachfile in *; do
        if [[ "$eachfile" =  *"serial"* ]]; then 
                echo USB serial file found. The name is "$eachfile"
                echo Would you like to use this file for persistant USB names? "(y) or (n)"
                file_exists_bool="1"
                read file_check_bool
                if [ $file_check_bool == "y" ]; then
                file=$eachfile
                fi
  fi
done

if [ $file_exists_bool == "0" ]; then
        cd $file_dir
        touch $file
fi

choose_rule_name(){
    echo Please either enter an integer corresponding to the list below.
    echo ""
    echo \(1\) diodes
    echo ""
    echo \(2\) heaters
    echo ""
    echo \(3\) lockin
    echo ""
    echo \(4\) warmup heaters
    echo ""
    echo \(5\) Custom    
    echo ""
    echo \(6\) Exit
    read user_rules_name_input
    if [ "$user_rules_name_input" == "1" ]; then
        sensor="diodes"
    elif [ "$user_rules_name_input" == "2" ]; then
        sensor="heaters"
    elif [ "$user_rules_name_input" == "3" ]; then
        sensor="lockin"
    elif [ "$user_rules_name_input" == "4" ]; then
        sensor="warmup heaters"
    elif [ "$user_rules_name_input" == "5" ]; then
        echo Please type the name you wish to assign the next microcontroller to
        read sensor  
    elif [ "$user_rules_name_input" == "6" ]; then
        echo Exiting Script
        add_rules_bool=0
        exit 0 
    fi     
}

#for sensor in "${sensor_list[@]}";do
while [ $add_rules_bool ];do
        choose_rule_name
        echo Please connect the micrcontroller to be used with "$sensor"
	      echo Please type "(y)" and enter once the microcontroller is connected within 30 seconds
       	read mc_connected      	
       	if [ $mc_connected == "y" ]; then
            
           	# Start timer to let others know when it's okay to plug the next mc in
           	SECONDS=0
           	
           	# Read microcontroller serial #
            serial_id=$(journalctl --dmesg --since "30 seconds ago" | grep -E -o  "SerialNumber:.*" | cut -c 15-31)
                
            # Check if sensor name already in file (used to replace mc serial #s)
            if grep -q "$sensor" "$file"; then ##note the space after the string you are searching for
        
                echo "$sensor" already found inside $file
                echo Do you want to replace the serial number already placed inside $file ?
		            echo Please answer with a "\(y\)" or a "\(n\)"
        
                read serial_replacment_bool
        
                if [ "$serial_replacment_bool" == "y" ]; then 
                    REPLACEMENT_TEXT_STRING="SUBSYSTEM==\"tty\", ATTRS{serial}==\"$serial_id\", SYMLINK+=\"$sensor\",MODE = \"0666\""
                    sed -i "/$sensor/c $REPLACEMENT_TEXT_STRING" /etc/udev/rules.d/$file
                else
                    echo This mc id will not be applied to "$sensor"
                    echo Moving onto the next sensor
                fi
                     
            # Microcontroller serial number not found in file, appending new rule to rules file
            else
                
                echo "$sensor" not found inside $file
                echo appending new sensor and mc serial number
		            echo ""
                echo "SUBSYSTEM==\"tty\", ATTRS{serial}==\"$serial_id\", SYMLINK+=\"$sensor\",MODE = \"0666\"" >> /etc/udev/rules.d/$file
        
            fi
            
            while [ $SECONDS -lt 30 ];do
                echo Please wait $((30 - $SECONDS)) seconds
                sleep 1s
            done
        else
            	echo "y" was not entered after connecting the microcontroller 
                echo Moving onto the next sensor
        fi
	echo ""
done

sudo udevadm control --reload-rules && sudo udevadm trigger
