from langcIQ import *
from pydantic import model_validator, ValidationError
import base64
import logging
logger = logging.getLogger(__name__)
load_dotenv()

class IQAgent(CustomChatModel): #Should inherit CustomChatModel,   

    username: Optional[str] = None
    """Username for capella"""

    password: Optional[str] = None
    """Password for capella"""

    hJWT: Optional[str] = None
    """JWT token"""

    def __init__(self, **data):
        super().__init__(**data) #i wonder why it works
        usr = self.username
        pas = self.password
        tok = self.hJWT

        if not (usr and pas) and not tok:
            raise ValidationError("Either username and password must be set or hJWT must be set.")   
        
        if not tok:
            to64 = usr+":"+pas
            byteData = to64.encode('ascii')
            encodedData = base64.b64encode(byteData)
            encodedString = encodedData.decode('ascii')
            #encodedString = encodedString[:-1] + "h" #for some reason, encoded str should end in h, but without this ends in = 
            #WOW its cuz the password was wrong :)))) &&& cuz copy and paste didnt get the ! :))))))))))

            #logger.warning("%s", encodedString)
            
            h = {"Authorization": f"Basic {encodedString}"}
            try:
                resp = requests.post(self.capAddy+"/sessions", headers=h)
                self.hJWT = "Bearer " + resp.json().get("jwt")
                
                #logger.warning("%s", self.hJWT)
            except:
                logger.error("Error in request for JWT token.")


    def setFields(self):
        if not self.hJWT:
                to64 = self.username+":"+self.password
                byteData = to64.encode('ascii')
                encodedData = base64.b64encode(byteData)
                encodedString = encodedData.decode('ascii')
                #encodedString = encodedString[:-1] + "h" #for some reason, encoded str should end in h, but without this ends in =

                #logger.warning("%s", encodedString)
                
                h = {"Authorization": f"Basic {encodedString}"}
                try:
                    resp = requests.post(self.capAddy+"/sessions", headers=h)
                    self.hJWT = "Bearer " + resp.json().get("jwt")
                except:
                    logger.error("Error in request for JWT token.")
                
                #logger.warning(self.hJWT)

    """       
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a very powerful assistant, with knowledge about Couchbase Server and Clusters."
            ),
            (
                "user",
                "{input}"
            ),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ]
    )"""
    #llm_w_tools = ChatOpenAI(model="gpt-3.5-turbo-0125", temperature=0).bind_tools(model.getTools())


    """agent = (
    {   
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_openai_tool_messages(
            x["intermediate_steps"]
        ),
    }   
    | prompt
    | model
    | OpenAIToolsAgentOutputParser()
    )

    agent_executor = AgentExecutor(agent=agent, tools=model.getTools(), verbose=True)

    self.lol.append(agent)
    self.lol.append(agent_executor)
        
def invoke(self, s):
    return self.lol[1].invoke({"input": s})"""

if __name__ == "__main__":
    test = IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))

    memory = Memory("cachedir")
    #@memory.cache
    def invoker(s):
        returnS = test.invoke(
            [
                #HumanMessage(content="hello!"),
                SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
                HumanMessage(content=s),
            ]
        )
        return returnS
    sT = time.time()
    s = invoker(input("input: "))
    eT = time.time()
    print(f"Time: {eT-sT}\n")
    print(s)    