"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""
import builtins
import edgir.common_pb2
import google.protobuf.descriptor
import google.protobuf.message
import typing
import typing_extensions

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor = ...

class BlockImpl(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
    META_FIELD_NUMBER: builtins.int
    @property
    def meta(self) -> edgir.common_pb2.Metadata: ...
    def __init__(self,
        *,
        meta : typing.Optional[edgir.common_pb2.Metadata] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> None: ...
global___BlockImpl = BlockImpl

class PortImpl(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
    META_FIELD_NUMBER: builtins.int
    @property
    def meta(self) -> edgir.common_pb2.Metadata: ...
    def __init__(self,
        *,
        meta : typing.Optional[edgir.common_pb2.Metadata] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> None: ...
global___PortImpl = PortImpl

class LinkImpl(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
    META_FIELD_NUMBER: builtins.int
    @property
    def meta(self) -> edgir.common_pb2.Metadata: ...
    def __init__(self,
        *,
        meta : typing.Optional[edgir.common_pb2.Metadata] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> None: ...
global___LinkImpl = LinkImpl

class EnvironmentImpl(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor = ...
    META_FIELD_NUMBER: builtins.int
    @property
    def meta(self) -> edgir.common_pb2.Metadata: ...
    def __init__(self,
        *,
        meta : typing.Optional[edgir.common_pb2.Metadata] = ...,
        ) -> None: ...
    def HasField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing_extensions.Literal[u"meta",b"meta"]) -> None: ...
global___EnvironmentImpl = EnvironmentImpl
