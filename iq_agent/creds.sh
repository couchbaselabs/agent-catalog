
CPADDR="https://api.dev.nonprod-project-avengers.com"
USERNAME="sahit.patnala@couchbase.com"
PASSWORD="..."
ORG_ID="6af08c0a-8cab-4c1c-b257-b521575c16d0"

# Replace the below values to your environment to test without providing any arguments
# : ${CPADDR:="https://api.dev.nonprod-project-avengers.com"}
# : ${USERNAME:="sahit.patnala@couchbase.com"}
# : ${PASSWORD:="xxxx"}
# : ${ORG_ID:="guid"}
#

BASE64PASS=$(printf ${USERNAME}:${PASSWORD} | base64)
JWT_TOKEN=$(curl -s ${CPADDR}/sessions -X POST -H "Authorization: Basic ${BASE64PASS}" | jq -r ".jwt")
echo ${JWT_TOKEN}