Model Module
============

The model module provides runtime representation of devices, channels, data points, and events.

Core Classes
------------

Device
~~~~~~

.. autoclass:: aiohomematic.model.device.Device
   :members:
   :undoc-members:
   :show-inheritance:

Channel
~~~~~~~

.. autoclass:: aiohomematic.model.device.Channel
   :members:
   :undoc-members:
   :show-inheritance:

Data Points
-----------

Base Data Point
~~~~~~~~~~~~~~~

.. autoclass:: aiohomematic.model.data_point.CallbackDataPoint
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: aiohomematic.model.data_point.BaseParameterDataPoint
   :members:
   :undoc-members:
   :show-inheritance:

Generic Data Points
~~~~~~~~~~~~~~~~~~~

.. automodule:: aiohomematic.model.generic
   :members:
   :undoc-members:
   :show-inheritance:

Custom Data Points
~~~~~~~~~~~~~~~~~~

.. automodule:: aiohomematic.model.custom
   :members:
   :undoc-members:
   :show-inheritance:
   :exclude-members: definition, support

Calculated Data Points
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: aiohomematic.model.calculated
   :members:
   :undoc-members:
   :show-inheritance:

Hub Entities
------------

.. automodule:: aiohomematic.model.hub
   :members:
   :undoc-members:
   :show-inheritance:

Events
------

.. autoclass:: aiohomematic.model.event.GenericEvent
   :members:
   :undoc-members:
   :show-inheritance:
