Protocol Interfaces
===================

The interfaces module defines protocol interfaces for dependency injection, reducing coupling between components.

Overview
--------

Protocol interfaces allow components to depend only on the specific functionality they need rather than the entire CentralUnit. This improves testability, reduces coupling, and makes dependencies explicit.

All protocol interfaces use Python's ``@runtime_checkable`` Protocol for structural subtyping.

Core Protocols
--------------

CentralInfo
~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.CentralInfo
   :members:
   :undoc-members:
   :show-inheritance:

ConfigProvider
~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.ConfigProvider
   :members:
   :undoc-members:
   :show-inheritance:

Client Protocols
----------------

ClientFactory
~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.ClientFactory
   :members:
   :undoc-members:
   :show-inheritance:

ClientProvider
~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.ClientProvider
   :members:
   :undoc-members:
   :show-inheritance:

PrimaryClientProvider
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.PrimaryClientProvider
   :members:
   :undoc-members:
   :show-inheritance:

Device & Channel Protocols
---------------------------

DeviceProvider
~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.DeviceProvider
   :members:
   :undoc-members:
   :show-inheritance:

ChannelLookup
~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.ChannelLookup
   :members:
   :undoc-members:
   :show-inheritance:

Data Point Protocols
--------------------

DataPointProvider
~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.DataPointProvider
   :members:
   :undoc-members:
   :show-inheritance:

Event Protocols
---------------

EventEmitter
~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.EventEmitter
   :members:
   :undoc-members:
   :show-inheritance:

EventBusProvider
~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.EventBusProvider
   :members:
   :undoc-members:
   :show-inheritance:

EventSubscriptionManager
~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.EventSubscriptionManager
   :members:
   :undoc-members:
   :show-inheritance:

Description Protocols
---------------------

DeviceDetailsProvider
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.DeviceDetailsProvider
   :members:
   :undoc-members:
   :show-inheritance:

DeviceDescriptionProvider
~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.DeviceDescriptionProvider
   :members:
   :undoc-members:
   :show-inheritance:

ParamsetDescriptionProvider
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.ParamsetDescriptionProvider
   :members:
   :undoc-members:
   :show-inheritance:

ParameterVisibilityProvider
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.ParameterVisibilityProvider
   :members:
   :undoc-members:
   :show-inheritance:

Infrastructure Protocols
------------------------

TaskScheduler
~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.TaskScheduler
   :members:
   :undoc-members:
   :show-inheritance:

FileOperations
~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.FileOperations
   :members:
   :undoc-members:
   :show-inheritance:

DataCacheProvider
~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.DataCacheProvider
   :members:
   :undoc-members:
   :show-inheritance:

Hub Protocols
-------------

HubDataFetcher
~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.HubDataFetcher
   :members:
   :undoc-members:
   :show-inheritance:

HubDataPointManager
~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.HubDataPointManager
   :members:
   :undoc-members:
   :show-inheritance:

Other Protocols
---------------

DeviceDataRefresher
~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.DeviceDataRefresher
   :members:
   :undoc-members:
   :show-inheritance:

SystemInfoProvider
~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.SystemInfoProvider
   :members:
   :undoc-members:
   :show-inheritance:

CoordinatorProvider
~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.CoordinatorProvider
   :members:
   :undoc-members:
   :show-inheritance:

CentralUnitStateProvider
~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.CentralUnitStateProvider
   :members:
   :undoc-members:
   :show-inheritance:

ClientCoordination
~~~~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.interfaces.ClientCoordination
   :members:
   :undoc-members:
   :show-inheritance:
