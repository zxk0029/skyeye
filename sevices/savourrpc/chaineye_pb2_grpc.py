# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from sevices.savourrpc import chaineye_pb2 as savourrpc_dot_chaineye__pb2


class ChaineyeServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.getArticleList = channel.unary_unary(
            '/savourrpc.chaineye.ChaineyeService/getArticleList',
            request_serializer=savourrpc_dot_chaineye__pb2.ArticleListReq.SerializeToString,
            response_deserializer=savourrpc_dot_chaineye__pb2.ArticleListRep.FromString,
        )
        self.getArticleDetail = channel.unary_unary(
            '/savourrpc.chaineye.ChaineyeService/getArticleDetail',
            request_serializer=savourrpc_dot_chaineye__pb2.ArticleDetailReq.SerializeToString,
            response_deserializer=savourrpc_dot_chaineye__pb2.ArticleDetailRep.FromString,
        )
        self.getCommentList = channel.unary_unary(
            '/savourrpc.chaineye.ChaineyeService/getCommentList',
            request_serializer=savourrpc_dot_chaineye__pb2.CommentListReq.SerializeToString,
            response_deserializer=savourrpc_dot_chaineye__pb2.CommentListRep.FromString,
        )
        self.getLikeAddress = channel.unary_unary(
            '/savourrpc.chaineye.ChaineyeService/getLikeAddress',
            request_serializer=savourrpc_dot_chaineye__pb2.AddressReq.SerializeToString,
            response_deserializer=savourrpc_dot_chaineye__pb2.AddressRep.FromString,
        )
        self.likeArticle = channel.unary_unary(
            '/savourrpc.chaineye.ChaineyeService/likeArticle',
            request_serializer=savourrpc_dot_chaineye__pb2.LikeReq.SerializeToString,
            response_deserializer=savourrpc_dot_chaineye__pb2.LikeRep.FromString,
        )


class ChaineyeServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def getArticleList(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getArticleDetail(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getCommentList(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def getLikeAddress(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def likeArticle(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_ChaineyeServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
        'getArticleList': grpc.unary_unary_rpc_method_handler(
            servicer.getArticleList,
            request_deserializer=savourrpc_dot_chaineye__pb2.ArticleListReq.FromString,
            response_serializer=savourrpc_dot_chaineye__pb2.ArticleListRep.SerializeToString,
        ),
        'getArticleDetail': grpc.unary_unary_rpc_method_handler(
            servicer.getArticleDetail,
            request_deserializer=savourrpc_dot_chaineye__pb2.ArticleDetailReq.FromString,
            response_serializer=savourrpc_dot_chaineye__pb2.ArticleDetailRep.SerializeToString,
        ),
        'getCommentList': grpc.unary_unary_rpc_method_handler(
            servicer.getCommentList,
            request_deserializer=savourrpc_dot_chaineye__pb2.CommentListReq.FromString,
            response_serializer=savourrpc_dot_chaineye__pb2.CommentListRep.SerializeToString,
        ),
        'getLikeAddress': grpc.unary_unary_rpc_method_handler(
            servicer.getLikeAddress,
            request_deserializer=savourrpc_dot_chaineye__pb2.AddressReq.FromString,
            response_serializer=savourrpc_dot_chaineye__pb2.AddressRep.SerializeToString,
        ),
        'likeArticle': grpc.unary_unary_rpc_method_handler(
            servicer.likeArticle,
            request_deserializer=savourrpc_dot_chaineye__pb2.LikeReq.FromString,
            response_serializer=savourrpc_dot_chaineye__pb2.LikeRep.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        'savourrpc.chaineye.ChaineyeService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


# This class is part of an EXPERIMENTAL API.
class ChaineyeService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def getArticleList(request,
                       target,
                       options=(),
                       channel_credentials=None,
                       call_credentials=None,
                       insecure=False,
                       compression=None,
                       wait_for_ready=None,
                       timeout=None,
                       metadata=None):
        return grpc.experimental.unary_unary(request, target, '/savourrpc.chaineye.ChaineyeService/getArticleList',
                                             savourrpc_dot_chaineye__pb2.ArticleListReq.SerializeToString,
                                             savourrpc_dot_chaineye__pb2.ArticleListRep.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getArticleDetail(request,
                         target,
                         options=(),
                         channel_credentials=None,
                         call_credentials=None,
                         insecure=False,
                         compression=None,
                         wait_for_ready=None,
                         timeout=None,
                         metadata=None):
        return grpc.experimental.unary_unary(request, target, '/savourrpc.chaineye.ChaineyeService/getArticleDetail',
                                             savourrpc_dot_chaineye__pb2.ArticleDetailReq.SerializeToString,
                                             savourrpc_dot_chaineye__pb2.ArticleDetailRep.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getCommentList(request,
                       target,
                       options=(),
                       channel_credentials=None,
                       call_credentials=None,
                       insecure=False,
                       compression=None,
                       wait_for_ready=None,
                       timeout=None,
                       metadata=None):
        return grpc.experimental.unary_unary(request, target, '/savourrpc.chaineye.ChaineyeService/getCommentList',
                                             savourrpc_dot_chaineye__pb2.CommentListReq.SerializeToString,
                                             savourrpc_dot_chaineye__pb2.CommentListRep.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def getLikeAddress(request,
                       target,
                       options=(),
                       channel_credentials=None,
                       call_credentials=None,
                       insecure=False,
                       compression=None,
                       wait_for_ready=None,
                       timeout=None,
                       metadata=None):
        return grpc.experimental.unary_unary(request, target, '/savourrpc.chaineye.ChaineyeService/getLikeAddress',
                                             savourrpc_dot_chaineye__pb2.AddressReq.SerializeToString,
                                             savourrpc_dot_chaineye__pb2.AddressRep.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def likeArticle(request,
                    target,
                    options=(),
                    channel_credentials=None,
                    call_credentials=None,
                    insecure=False,
                    compression=None,
                    wait_for_ready=None,
                    timeout=None,
                    metadata=None):
        return grpc.experimental.unary_unary(request, target, '/savourrpc.chaineye.ChaineyeService/likeArticle',
                                             savourrpc_dot_chaineye__pb2.LikeReq.SerializeToString,
                                             savourrpc_dot_chaineye__pb2.LikeRep.FromString,
                                             options, channel_credentials,
                                             insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
