from .langcIQ import IQChatModel, Optional, requests, logging, time, HumanMessage, SystemMessage, os
from pydantic import model_validator, ValidationError
import base64
import logging


class IQBackedChatModel(IQChatModel): #Should inherit CustomChatModel,   

    username: Optional[str] = None
    """Username for capella"""

    password: Optional[str] = None
    """Password for capella"""

    jwt: Optional[str] = None
    """JWT token"""

    def __init__(self, **data):
        super().__init__(**data)
        usr = self.username
        pas = self.password
        tok = self.jwt

        if not (usr and pas) and not tok:
            raise TypeError("Either username and password must be set or hJWT must be set.")   
        
        if not tok:
            to64 = usr+":"+pas
            byteData = to64.encode('ascii')
            encodedData = base64.b64encode(byteData)
            encodedString = encodedData.decode('ascii')


            #logger.warning("%s", encodedString)
            
            header = {"Authorization": f"Basic {encodedString}"}
            try:
                resp = requests.post(self.capella_address+"/sessions", headers=header)
                self.jwt = "Bearer " + resp.json().get("jwt")
                
                #logger.warning("%s", self.hJWT)
            except:
                logging.error("Error in request for JWT token.")



if __name__ == "__main__":    
    from dotenv import load_dotenv, dotenv_values 
    load_dotenv()

    test = IQBackedChatModel(model_name="custam",capella_address=os.getenv("CAPELLA-ADDRESS"), org_id=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))

    def invoker(s):
        returnS = test.invoke(
            [
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