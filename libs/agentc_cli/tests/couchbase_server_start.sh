# This is a script to spin up a couchbase server
# and create a cluster for unit tests

# Remove existing container with same name
docker rm -f smoke_tests_db

# Start server from latest couchbase docker image
echo "Starting Couchbase container..."
docker run -d --name smoke_tests_db -p 8091-8096:8091-8096 -p 11210-11211:11210-11211 couchbase
if [ $? -ne 0 ]; then
  echo "Failed to start Couchbase container!"
  exit 1
fi

echo "Waiting for Couchbase to initialize..."
sleep 10

# Initialise cluster
echo "Initializing Couchbase cluster..."
curl -v -X POST http://localhost:8091/clusterInit \
  -d "username=Administrator" \
  -d "password=password" \
  -d "sendStats=true" \
  -d "clusterName=agentc" \
  -d "services=kv,n1ql,index,fts" \
  -d port='SAME' \
  -d indexerStorageMode='plasma'
if [ $? -ne 0 ]; then
  echo "Failed to initialize cluster!"
  exit 1
fi

# Import travel-sample bucket
echo "Importing travel-sample bucket..."
curl -v -X POST -u Administrator:password \
   http://localhost:8091/sampleBuckets/install \
   -d '["travel-sample"]' | jq .

if [ $? -ne 0 ]; then
  echo "Failed to import travel-sample bucket!"
  exit 1
fi

echo "Couchbase setup complete. Cluster and travel-sample bucket successfully initialized!"

#docker stop smoke_tests_db