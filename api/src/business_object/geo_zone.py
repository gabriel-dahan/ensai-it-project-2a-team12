
class GeographicZone:
    id; optional[str]
    name: str
    def getmunicipalities(self)->list["Municipality"]:
     """Return the flat list of municipalities covered by this zone.
 
        Overridden by subclasses; the base zone has no municipalities.
        """
        return []
 

class Region:
     insee_code: str
    departments: list["Department"] = field(default_factory=list)
 
    def add_department(self, department: "Department") -> None:
        department.region = self
        self.departments.append(department)
    def get_municipalities(self) -> list["Municipality"]:
        return [m for dept in self.departments for m in dept.get_municipalities()]
    

class Department:
    
    

class Municipality:
    ...

class Zoning:
    ...