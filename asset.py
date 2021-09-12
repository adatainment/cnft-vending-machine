from typing import List

class Asset:                                                           
    def __init__(self, name: str, amount: int):                        
        self.name = name                                               
        self.amount = amount                                           
                                                                       
    def __str__(self):                                                 
        return f'{self.amount} {self.name}'                            
                                                                       
    def __repr__(self):                                                
        return f'Asset {{ Name: {self.name}, Amount: {self.amount} }}' 
                                                                       
def get_multi_asset_str(assets: List[Asset]) -> str:                   
    asset_strings = list(map(lambda a: f'{a.amount} {a.name}', assets))
    return " + ".join(asset_strings)                                   
                                                                       
def get_assets_from_str(multi_asset_str: str) -> List[Asset]:          
    tokens = list(filter(None, multi_asset_str.split(" ")))            
    assetStrs = list(filter(lambda s: s != "+", tokens))               
    assets = []                                                        
    for i in range(int(len(assetStrs)/2)):                             
        assets.append(Asset(assetStrs[i*2+1], int(assetStrs[i*2])))    
    return assets                                                      