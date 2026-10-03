from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase): #creates application specific parent class
    # future models will inherit from Base
    # declarativeBase gives Base a shared metadata registry
    # doesnt create db table, only establishes python side model registry
    pass

