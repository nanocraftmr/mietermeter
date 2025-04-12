cat /sys/class/net/eth0/address

sudo apt install git 

git clone https://github.com/nanocraftmr/mietermeter

cd mietermeter

#secure env + hdg, user, camera from outside

docker-compose build

docker-compose up -d