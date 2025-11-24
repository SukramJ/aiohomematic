Client Module
=============

The client module provides protocol adapters for communicating with Homematic CCU and compatible backends via XML-RPC and JSON-RPC.

Client Base Classes
-------------------

.. autoclass:: aiohomematic.client.Client
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: aiohomematic.client.ClientConfig
   :members:
   :undoc-members:
   :show-inheritance:

Client Implementations
----------------------

.. autoclass:: aiohomematic.client.ClientCCU
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: aiohomematic.client.ClientJsonCCU
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: aiohomematic.client.ClientHomegear
   :members:
   :undoc-members:
   :show-inheritance:

Configuration
-------------

.. autoclass:: aiohomematic.client.InterfaceConfig
   :members:
   :undoc-members:
   :show-inheritance:

Factory Functions
-----------------

.. autofunction:: aiohomematic.client.create_client
