import pydantic
import re

from agentc_core.tool import tool


# Tools in Agent Catalog are decorated with `@tool`.
# Python tools, at a minimum, must contain a docstring (the string immediately below the function name line).
@tool
def check_if_airport_exists(aita_code: str) -> bool:
    """Check if the given AITA code is valid (i.e., represents an airline)."""
    return (
        re.match(
            r"MRS|NCE|CDG|ATL|AMS|MNL|NIB|GYE|LYS|TCT|TLS|TLV|TNR|TPA|TPE|TRI|TRN|TUL|TUN|MCG|TUS|TXL|TYS|UIO|VCE|VGO|"
            r"VIE|VLC|VLD|VPS|CAN|ENH|MRU|TLJ|ORY|BOD|ETZ|LHR|LIL|ALG|AAE|CZL|ORN|MLH|BJA|BLJ|BSK|QSF|TLM|DEL|EWR|BHX|"
            r"JFK|ORD|BOM|SFO|NRT|EZE|LAX|DFW|HKG|ICN|MIA|PUJ|ABY|ALB|BDL|BNA|BOS|BWI|CLE|CMH|CUN|CVG|CZM|DCA|DEN|DTW|"
            r"FCO|GDL|IAD|IND|JAX|LGA|MAD|MCI|MCO|MEM|MEX|MSP|MSY|MTY|PHL|PIT|PVR|RDU|RIC|SEA|SJD|SLC|STL|XNA|YUL|FAT|"
            r"ONT|SJC|SMF|PHX|HMO|MZT|ZIH|ZLO|IAH|LAS|SAT|MID|SAN|BJX|MLM|CTA|LIN|PMO|LGW|ANC|ADK|ADQ|AKN|ANI|BET|BRW|"
            r"CDB|CDV|DLG|ENA|FAI|HNL|HOM|JNU|KSM|OME|OTZ|PDX|SCC|SDP|SNP|STG|UNK|VDZ|BHM|CHS|CLT|GSO|HSV|JAN|ORF|PBI|"
            r"PNS|RSW|SAV|LWS|ISP|PBG|PQI|YAK|SNA|HLN|GTF|BLI|OAK|KTN|PSG|SIT|WRG|ABQ|AUS|ZRH|ELP|KOA|LIH|LTO|MFR|MMH|"
            r"MRY|OGG|OKC|RNO|SAF|STS|YVR|BOI|PUW|BIL|BUR|EUG|GEG|LGB|MSO|PSC|PSP|RDM|SBA|ALW|BZN|COS|EAT|FCA|FLL|OMA|"
            r"YEG|YKM|YLW|YYC|YYJ|CMN|RAK|NTE|SXB|TNG|AGA|ESU|FEZ|OUD|OZZ|RBA|SJO|SAL|BOG|MDE|HAM|SAP|GUA|CGN|DUS|STR|"
            r"BAQ|CLO|CTG|LIM|BRS|VRN|WAW|WUH|YYZ|ZAG|ZSE|MKE|SJU|HEL|FRA|MAN|BCN|DUB|LCY|BIA|MXP|ARN|LIS|CLY|EDI|CWL|"
            r"GLA|HUY|LBA|MME|NWI|AVL|BUF|CAE|CHA|DAY|GNV|GPT|HOU|ICT|ILM|LIT|MYR|PTY|ROC|SRQ|ABJ|ABZ|BES|BIO|BKK|BLL|"
            r"BLQ|BRE|CFE|CPH|DKR|DXB|EVN|FLR|GOA|GOT|HAJ|HAN|JNB|MPL|NAP|NCL|NUE|OSL|PRG|PUF|RNS|SCL|SGN|SVG|SXM|STN|"
            r"AJA|FSC|MSQ|NQY|WIL|MBA|WJR|MYD|HAH|NBO|MGQ|ASV|KTL|LAU|LKG|MRE|UKA|HGA|AUA|NAS|PLS|SDQ|STI|STT|HPN|KIN|"
            r"MBJ|ORH|PAP|POS|PVD|SWF|AZS|BDA|BGI|BQN|BTV|GCM|LIR|LRM|POP|PSE|PWM|SYR|UVF|STX|AAR|AAL|BMA|SKB|TAB|MCT|"
            r"DOH|GSP|CNX|HKT|BGO|BRU|MUC|CNS|MLE|BNE|DUR|PLZ|BAH|CPT|ROB|VNO|HRE|LVI|VFA|WDH|AGP|GRX|IBZ|IOM|MAH|PMI|"
            r"RTM|ACE|ALC|ANU|BRI|DBV|FAO|JER|LCA|MLA|OLB|PFO|PSA|SKG|SZG|TFS|TIA|ABV|ACC|ALA|AMM|ATH|AUH|BEY|BHD|BLR|"
            r"BSL|BUD|CAI|CTU|DME|EBB|FNA|GIB|GIG|GRU|GVA|GYD|HND|HYD|IST|JED|JMK|JTR|KBP|KWI|LAD|LED|LOS|LUX|MAA|OPO|"
            r"OTP|PEK|PVG|RUH|SIN|SOF|TIP|CUR|CMB|SYD|GND|DOM|EIS|FDF|PTP|VIJ|VQS|NEV|SSB|SPB|KOI|LSI|EXT|SOU|EMA|INV|"
            r"SYY|GCI|NOC|WAT|CFN|WIC|EGC|BEB|BRR|CAL|ILY|TRE|JYV|KAJ|KEM|KOK|MHQ|NRK|SVL|TAY|LPL|DSA|LIG|LRH|DND|DAC|"
            r"ZYL|DJE|MIR|TSN|CSX|DYG|XNN|CJU|CKG|HGH|HJJ|KMG|LLF|NKG|SYX|TAO|TEN|XIY|XMN|ZHA|YNT|HRB|OHE|DLC|HEK|JGD|"
            r"JMU|JXA|HFE|JHG|UYN|SHE|SZX|NGB|ZUH|NNG|HET|KWL|URC|RIX|GEO|AKP|CXF|IRC|FYU|BTT|CEM|CIK|MLY|RMP|TAL|WBQ|"
            r"MNT|AVN|KIX|SCU|FUE|ZTH|PHC|DMM|JRO|KGL|ABE|AEX|AGS|ATW|AVP|AZO|BMI|BON|BQK|BSB|BTR|BZE|CAK|CCS|CHO|CID|"
            r"CRW|CSG|DAB|DAL|DHN|DSM|ECP|EVV|EWN|EYW|FAR|FAY|FNT|FPO|FSD|FSM|FWA|GGT|GRB|GRK|GRR|GTR|LAN|LEX|LFT|MBS|"
            r"MDT|MDW|MGA|MGM|MHT|MLB|MLI|MLU|MOB|MSN|OAJ|PHF|PIA|ROA|RTB|SBN|SDF|SGF|SHV|TGU|TLH|DWC|INL|NIM|APN|BGM|"
            r"BGR|CIU|CWA|ELM|ERI|ESC|ITH|MQT|NGO|PLN|SCE|TVC|YOW|RKS|HAV|ABR|CUL|FUK|LUN|SVO|REP|RHI|BRD|DAR|GUM|BTS|"
            r"MEL|PPT|YHZ|ACA|BIS|BJI|BTM|CDC|CNY|COD|CPR|DIK|DLH|EKO|GCC|VSA|GFK|HIB|IMT|ISN|LNK|LSE|MOT|RAP|RST|YQR|"
            r"YWG|YXE|CUU|OUA|ROR|SPN|GJT|IDA|JAC|KSC|PIH|SGU|TWF|VEL|AES|LPA|SPU|TOS|TRD|TRF|ORK|SNN|BLK|BOH|PGF|SEN|"
            r"ELQ|TIF|TUU|YNB|HBE|ADD|LEJ|CDR|FMN|TTN|PIR|WRL|LBL|AIA|ALS|BKG|CYS|ILG|SOW|PGA|IGM|DDC|ATY|HON|UST|KEF|"
            r"SFB|APW|CXI|NAN|HRL|LBB|AMA|MAF|CRP|SHG|ATK|BEG|TLT|CHU|HCR|KLG|RSH|SHX|KGX|AIN|EMK|SXP|CYF|EEK|BVA|HPB|"
            r"LTN|KKH|PIK|KUK|KWK|KWN|KWT|MLL|NME|OOK|PQS|VAK|WTL|DRG|NUI|PIZ|CKD|LDE|RDV|SLQ|KPN|BZG|GDN|KRK|KTW|KUN|"
            r"LDY|BKC|MJV|REU|CRL|NYO|CCF|KKA|AUK|KOT|CIA|SVQ|CHQ|GRO|RHO|BZR|GAL|RBY|BTI|BGY|POZ|RZE|TSF|WMI|WRO|HSL|"
            r"KAL|NUL|AHO|BDS|SVA|CAG|GSE|NDR|PSR|PUY|WMO|RYG|TPS|TRS|ZAD|ZAZ|ANV|NRN|SCM|EIN|KYU|ORV|ELI|SKK|BIQ|FNI|"
            r"RDZ|WBB|MOU|TUF|TLA|WAA|CFU|HHN|NUP|SDR|ABL|DNR|TOG|LEI|SXF|EBU|TNK|ATT|GAM|GLV|KTS|SHH|MYU|IAN|KGS|HYL|"
            r"PHO|DLE|WLK|WTK|SZZ|KIR|TLL|CGA|OBU|KTB|SRV|AKI|XCR|WWT|AOI|BRQ|BVE|CIY|DTM|KVL|EFL|SMK|PIS|FKB|FMM|HAU|"
            r"LNZ|LUZ|MMX|OSI|OSR|PDV|PEG|PMF|SCQ|SFT|SUF|TGD|TLN|TMP|VST|XRY|MTM|SFA|PGD|PIE|AZA|GRI|PVU|RFD|STC|LRD|"
            r"MFE|SCK|SMX|HTS|YNG|IAG|SPI|TOL|LCK|BLV|CKB|HGR|OWB|PSM|ACI|HAK|LYA|TNC|DSN|KHN|KWE|SWA|HLD|TYN|LYI|LHW|"
            r"CGO|INC|SJW|HIA|WNZ|AQG|BHY|CGD|LZO|TXN|CIF|HLH|NZH|RLK|TGO|WUA|XIL|FOC|YIW|KOW|MIG|DNH|IQN|JGN|YZY|LUR|"
            r"JJN|DAT|MDG|TNA|BAV|CGQ|FUG|MWX|SHA|CIH|AAT|AKU|HMI|HTN|KCA|KHG|KRL|KRY|NLT|TCG|YIN|NAO|YIH|DUT|KLL|PIP|"
            r"WSN|KFP|KVC|NLG|AKB|IKO|KQA|KCQ|KPV|IGG|EGX|AKL|ITO|LNY|MKK|PPG|SDJ|CTS|TAS|UGC|OVD|LCG|TFN|IKA|HUS|VEE|"
            r"AET|KBC|ARC|BEL|CNF|MAO|REC|SSA|LJU|OKA|KLW|WWP|PPV|HYG|KCC|KPB|AHN|MKL|IPL|ELD|HOT|HNH|GST|SGY|HNS|HRO|"
            r"SLN|OTH|PDT|TSE|TVF|EWB|HYA|MVY|MSS|OGS|GDV|GGW|HVR|OLF|SDY|ACK|AUG|BHB|LEB|PVC|RKD|RUT|SLK|KCL|PTH|DLA|"
            r"AXA|CPX|MAZ|CGI|IRK|MWA|TBN|UIN|ILI|CYB|BZV|PNR|ANG|BFS|YYT|KIV|EOI|NDY|NRL|PPW|SOY|WRY|DLM|BLA|BJV|FNC|"
            r"HER|CNM|LAM|LNS|VCT|CLM|ESD|BFI|RCE|WSX|FRD|LKE|FBS|YWH|DHB|LPS|KUL|LXR|JHM|HNM|MUE|ACY|AXM|LBE|TLC|ZSA|"
            r"RAR|LWB|MCN|MEI|MSL|PIB|RJK|DCM|TUP|PMY|SLA|AEP|AGF|LUK|MMU|MBL|SAW|CFR|ADB|BIM|YTZ|ELH|YKS|CKH|CYX|IKS|"
            r"ULK|FSP|ISB|LHE|KHI|AUR|LAI|LRT|UIP|GHB|MHH|SBH|SFG|TCB|TBS|HKB|FRU|OSS|CEK|KJA|KRR|OVB|SVX|SGC|ADL|CBR|"
            r"DRW|PER|TSV|IAS|CGP|CCU|CXB|JSR|PDL|MAB|GYN|CMP|MQH|IMP|OIA|RDC|CKS|CDJ|SXO|GRP|NOU|WLS|VLI|FUT|FLO|SID|"
            r"BVC|RUN|DZA|HHH|LYH|PGV|SBY|SLU|CAY|POA|CEG|ERF|PRN|AGB|XFW|GLH|ABI|ACT|AGU|ALO|AQP|ART|ASP|ASU|BFL|BJL|"
            r"BPT|BRO|STZ|SXX|CHC|CLL|DIJ|ASB|PGX|LEH|NBE|AYT|HRG|SSH|CMI|CCC|COU|DRO|GCK|GGG|TEB|JLN|LAW|LCH|MHK|PBC|"
            r"CWB|DBQ|QRO|KOE|ROW|SJT|PVK|SLP|SPS|TRC|TXK|TYR|HOG|VDA|ZCL|YQB|YQM|TOE|MOF|DRS|FLG|INN|KLX|SCY|LFW|CEC|"
            r"JST|JHW|SHD|BJM|COO|NSI|ACV|MGW|BFD|DUJ|FKL|PKB|ASE|EGE|GUC|HDN|LAR|MTJ|PUB|YMM|CKY|FIH|HVN|IPT|AOO|ITM|"
            r"BKW|CIC|CLD|OKJ|ROP|TKK|YAP|MAJ|LGK|PEN|CME|DGO|HOB|HUX|OAX|SLW|TAM|VER|CMX|EAU|KWA|PNI|KSA|SBP|YUM|TMS|"
            r"FOE|MKG|JUL|KHH|PAH|YXU|LMT|MOD|RDD|LPY|VKO|VVI|LPB|MVD|SUX|YKF|NOS|TMM|MAR|GLO|RAI|VXE|PUS|CLJ|TGM|TSR|"
            r"BOJ|CRA|DEB|IEV|SKP|VAR|ANR|DOL|EXI|KAE|LGG|PUQ|PMC|STM|KBV|LPQ|BGF|BKO|JIB|LBV|NDJ|NKC|LXA|SSG|KTT|CGK|"
            r"LLW|NBS|IVL|LJG",
            aita_code,
        )
        is not None
    )


# It is highly recommended to use Pydantic models to define the input and output types of your tools.
# The Pydantic models below belong to dummy tools, but illustrate what example travel-tools might look like.
class FlightDeal(pydantic.BaseModel):
    airline: str
    price: float
    departure: str
    arrival: str
    duration: str
    stops: int


class PackingChecklistItem(pydantic.BaseModel):
    item: str
    quantity: int
    packed: bool


class Hotel(pydantic.BaseModel):
    name: str
    address: str
    price_per_night: float
    rating: float


class WeatherForecast(pydantic.BaseModel):
    date: str
    temperature: float
    condition: str


class TravelCost(pydantic.BaseModel):
    distance: float
    fuel_efficiency: float
    fuel_price: float
    total_cost: float


class LocalRestaurant(pydantic.BaseModel):
    name: str
    address: str
    cuisine: str
    rating: float


class TouristAttraction(pydantic.BaseModel):
    name: str
    description: str
    address: str
    rating: float


class CurrencyExchangeRate(pydantic.BaseModel):
    currency_from: str
    currency_to: str
    rate: float


class TravelItinerary(pydantic.BaseModel):
    destinations: list[str]
    duration: int
    activities: list[str]


class TravelInsuranceOption(pydantic.BaseModel):
    provider: str
    plan_name: str
    coverage_amount: float
    price: float


class PublicTransportationRoute(pydantic.BaseModel):
    route_number: str
    start_point: str
    end_point: str
    schedule: str


class TravelRestriction(pydantic.BaseModel):
    country: str
    restriction_details: str
    last_updated: str


class CarRentalService(pydantic.BaseModel):
    company: str
    car_model: str
    price_per_day: float
    availability: bool


class TravelAdvice(pydantic.BaseModel):
    destination: str
    advice: str
    last_updated: str


class LocalEvent(pydantic.BaseModel):
    name: str
    location: str
    date: str
    description: str


@tool
def search_best_flight_deals() -> list[FlightDeal]:
    """Search for the best flight deals."""
    return None


@tool
def create_packing_checklist() -> list[PackingChecklistItem]:
    """Create a packing checklist."""
    return None


@tool
def organize_travel_documents() -> None:
    """Organize all of your travel documents."""
    return None


@tool
def setup_out_of_office_reply() -> None:
    """Set up an out-of-office email reply."""
    return None


@tool
def find_hotel_by_location(location: str) -> list[Hotel]:
    """Find hotels in a specific location"""
    return None


@tool
def get_weather_forecast(destination: str) -> WeatherForecast:
    """Get the weather forecast for a travel destination"""
    return None


@tool
def calculate_travel_costs(distance: float, fuel_efficiency: float, fuel_price: float) -> TravelCost:
    """Calculate the travel costs based on distance, fuel efficiency, and fuel price"""
    return None


@tool
def search_local_restaurants(city: str) -> list[LocalRestaurant]:
    """Search for local restaurants in a given city"""
    return None


@tool
def find_tourist_attractions(destination: str) -> list[TouristAttraction]:
    """Find popular tourist attractions in a travel destination"""
    return None


@tool
def book_flight(ticket_info: dict) -> None:
    """Book a flight using the provided ticket information"""
    return None


@tool
def get_currency_exchange_rate(currency_from: str, currency_to: str) -> CurrencyExchangeRate:
    """Get the currency exchange rate between two currencies"""
    return None


@tool
def create_travel_itinerary(destinations: list, duration: int) -> TravelItinerary:
    """Create a travel itinerary based on a list of destinations and duration"""
    return None


@tool
def find_travel_insurance_options(traveler_info: dict) -> list[TravelInsuranceOption]:
    """Find travel insurance options based on traveler information"""
    return None


@tool
def get_public_transportation_routes(city: str) -> list[PublicTransportationRoute]:
    """Get public transportation routes in a specific city"""
    return None


@tool
def check_travel_restrictions(country: str) -> list[TravelRestriction]:
    """Check travel restrictions for a specific country"""
    return None


@tool
def find_car_rental_services(location: str) -> list[CarRentalService]:
    """Find car rental services in a specific location"""
    return None


@tool
def get_travel_advice(destination: str) -> list[TravelAdvice]:
    """Get travel advice for a specific destination"""
    return None


@tool
def find_local_events(city: str, date: str) -> list[LocalEvent]:
    """Find local events happening in a city on a specific date"""
    return None
