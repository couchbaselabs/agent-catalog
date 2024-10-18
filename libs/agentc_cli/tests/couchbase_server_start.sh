# This is a script to spin up a couchbase server
# and create a cluster for unit tests

# Remove existing container with same name
docker rm -f smoke_tests_db

# Start server from latest couchbase docker image
docker run -d --name smoke_tests_db -p 8091-8096:8091-8096 -p 11210-11211:11210-11211 couchbase
sleep 5

# Initialise cluster
curl -X POST http://localhost:8091/clusterInit \
  -d "username=Administrator" \
  -d "password=password" \
  -d "sendStats=true" \
  -d "clusterName=agentc" \
  -d "services=kv,n1ql,index,fts" \
  -d port='SAME' \
  -d indexerStorageMode='plasma'
sleep 5

# Import travel-sample bucket
curl -X POST -u Administrator:password \
   http://localhost:8091/sampleBuckets/install \
   -d '["travel-sample"]' | jq .

#docker stop smoke_tests_db