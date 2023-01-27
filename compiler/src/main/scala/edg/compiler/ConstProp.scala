package edg.compiler

import scala.collection.mutable
import scala.collection.Set
import edgir.expr.expr
import edgir.init.init
import edg.wir._
import edg.util.{DependencyGraph, MutableBiMap}
import edg.ExprBuilder
import edgir.ref.ref.LocalPath


case class AssignRecord(target: IndirectDesignPath, root: DesignPath, value: expr.ValueExpr)

case class OverassignRecord(assigns: mutable.Set[(DesignPath, String, expr.ValueExpr)] = mutable.Set())


sealed trait ConnectedLinkRecord  // a record in the connected link directed graph
object ConnectedLinkRecord {
  // a connection that is directly to a link, with the graph value being the path to the link itself
  case class ConnectedLink(port: DesignPath) extends ConnectedLinkRecord
  // for a connect that isn't directly to a link, lowers into ConnectedLink once the final destination is known
  case class Connected(port: DesignPath, nextPortToLink: DesignPath) extends ConnectedLinkRecord
}


sealed trait ConnectedLinkResult  // a result for resolving connected links
object ConnectedLinkResult {
  case class ResolvedPath(path: IndirectDesignPath) extends ConnectedLinkResult
  case class MissingConnectedLink(port: DesignPath) extends ConnectedLinkResult
}


/**
  * Parameter propagation, evaluation, and resolution associated with a single design.
  * General philosophy: this should not refer to any particular design instance, so the design can continue to be
  * transformed (though those transformations must be strictly additive with regards to assignments and assertions)
  *
  * This class resolves CONNECTED_LINK references once the connections are known, though
  * parameters on connected ports must be manually propagated via addEquality.
  * addEquality is idempotent and may be repeated.
  */
class ConstProp(frozenParams: Set[IndirectDesignPath] = Set()) {
  // Assign statements logged here on addAssignment
  private val paramAssign = mutable.HashMap[IndirectDesignPath, AssignRecord]()
  // Param source, for error tracking
  private val paramSource = mutable.HashMap[IndirectDesignPath, (DesignPath, String, expr.ValueExpr)]()

  // Assign statements are added to the dependency graph only when arrays are ready
  // This is the authoritative source for the state of any param - in the graph (and its dependencies), or value solved
  // CONNECTED_LINK has an empty value but indicates that the path was resolved in that data structure
  private val params = DependencyGraph[IndirectDesignPath, ExprValue]()
  private val paramTypes = mutable.HashMap[DesignPath, Class[_ <: ExprValue]]()  // only record types of authoritative elements

  private val connectedLink = DependencyGraph[ConnectedLinkRecord, DesignPath]()  // tracks the port -> link paths

  // Params that have a forced/override value, and the name and target expr.
  // The value is tracked so we know which expr takes precedence.
  private val forcedParams = mutable.Map[IndirectDesignPath, (String, expr.ValueExpr)]()

  // Overassigns, for error tracking
  // This only tracks overassigns that were discarded, not including assigns that took effect.
  // Additional analysis is needed to get the full set of conflicting assigns.
  private val discardOverassigns = mutable.HashMap[IndirectDesignPath, OverassignRecord]()

  def initFrom(that: ConstProp, forcedValues: Map[DesignPath, (ExprValue, String)] = Map()): Unit = {
    require(paramAssign.isEmpty && paramSource.isEmpty && paramTypes.isEmpty && forcedParams.isEmpty
      && discardOverassigns.isEmpty)
    paramAssign.addAll(that.paramAssign)
    paramSource.addAll(that.paramSource)
    params.initFrom(that.params)
    paramTypes.addAll(that.paramTypes)
    connectedLink.initFrom(that.connectedLink)
    forcedParams.addAll(that.forcedParams)
    discardOverassigns.addAll(that.discardOverassigns)
    forcedValues.foreach { case (forcedPath, (forcedValue, forcedName)) =>
      setForcedValue(forcedPath, forcedValue, forcedName, false)
    }
    update() // for when frozenParams changes
  }

  //
  // Callbacks, to be overridden at instantiation site
  //
  def onParamSolved(param: IndirectDesignPath, value: ExprValue): Unit = { }


  // For some path, return the concrete path resolving CONNECTED_LINK as applicable
  protected def resolveConnectedLink(path: IndirectDesignPath): ConnectedLinkResult = {
    path.splitConnectedLink match {
      case Some((connected, postfix)) =>
        connectedLink.getValue(ConnectedLinkRecord.ConnectedLink(connected)) match {
          case Some(connectedLinkPath) =>
            resolveConnectedLink(connectedLinkPath.asIndirect ++ postfix)
          case None =>
            ConnectedLinkResult.MissingConnectedLink(connected)
        }
      case None => ConnectedLinkResult.ResolvedPath(path)
    }
  }

  //
  // Processing Code
  //
  // Repeated does propagations as long as there is work to do, including both array available and param available.
  protected def update(): Unit = {
    while (connectedLink.getReady.nonEmpty) {
      val ready = connectedLink.getReady.head
      ready match {
        case ConnectedLinkRecord.Connected(port, nextPortToLink) => // propagate connected link
          connectedLink.setValue(ConnectedLinkRecord.ConnectedLink(port),
            connectedLink.getValue(ConnectedLinkRecord.ConnectedLink(nextPortToLink)).get)
          params.setValue(port.asIndirect + IndirectStep.ConnectedLink, BooleanValue(false))  // dummy value
        case _ => throw new IllegalArgumentException()
      }
      connectedLink.setValue(ready, DesignPath())
    }

    var readyList = Set[IndirectDesignPath]()
    do {
      // ignore params where we haven't seen the decl yet, to allow forced-assign when the block is expanded
      readyList = (params.getReady -- frozenParams).filter { elt =>
        DesignPath.fromIndirectOption(elt) match {
          case Some(elt) => paramTypes.keySet.contains(elt)
          case None => true
        }
      }
      readyList.foreach { constrTarget =>
        val assign = paramAssign(constrTarget)
        new ExprEvaluatePartial(this, assign.root).map(assign.value) match {
          case ExprResult.Result(result) =>
            params.setValue(constrTarget, result)
            onParamSolved(constrTarget, result)
          case ExprResult.Missing(missing) => // account for CONNECTED_LINK prefix
            val missingCorrected = missing.map { path =>
              resolveConnectedLink(path) match {
                case ConnectedLinkResult.ResolvedPath(path) => path
                case ConnectedLinkResult.MissingConnectedLink(portPath) => portPath.asIndirect + IndirectStep.ConnectedLink
              }
            }
            params.addNode(constrTarget, missingCorrected.toSeq, update = true)
        }
      }
    } while (readyList.nonEmpty)
  }

  //
  // API methods
  //
  def addDeclaration(target: DesignPath, decl: init.ValInit): Unit = {
    require(!paramTypes.isDefinedAt(target), s"redeclaration of $target")
    val paramType = decl.`val` match {
      case init.ValInit.Val.Floating(_) => classOf[FloatValue]
      case init.ValInit.Val.Integer(_) => classOf[IntValue]
      case init.ValInit.Val.Boolean(_) => classOf[BooleanValue]
      case init.ValInit.Val.Text(_) => classOf[TextValue]
      case init.ValInit.Val.Range(_) => classOf[RangeType]
      case init.ValInit.Val.Array(arrayType) => arrayType.`val` match {
        case init.ValInit.Val.Floating(_) => classOf[ArrayValue[FloatValue]]
        case init.ValInit.Val.Integer(_) => classOf[ArrayValue[IntValue]]
        case init.ValInit.Val.Boolean(_) => classOf[ArrayValue[BooleanValue]]
        case init.ValInit.Val.Text(_) => classOf[ArrayValue[TextValue]]
        case init.ValInit.Val.Range(_) => classOf[ArrayValue[RangeType]]
        case _ => throw new NotImplementedError(s"Unknown init array-type $decl")
      }
      case _ => throw new NotImplementedError(s"Unknown param declaration / init $decl")
    }
    paramTypes.put(target, paramType)
    update()
  }

  def setConnectedLink(linkPath: DesignPath, portPath: DesignPath): Unit = {
    connectedLink.setValue(ConnectedLinkRecord.ConnectedLink(portPath), linkPath)
    params.setValue(portPath.asIndirect + IndirectStep.ConnectedLink, BooleanValue(false))  // dummy value

    update()
  }

  def setConnection(toLinkPortPath: DesignPath, toBlockPortPath: DesignPath): Unit = {
    connectedLink.addNode(ConnectedLinkRecord.Connected(toBlockPortPath, toLinkPortPath),
      Seq(ConnectedLinkRecord.ConnectedLink(toLinkPortPath)))

    update()
  }

  /**
    * Adds a directed assignment (param <- expr) and propagates as needed
    */
  def addAssignExpr(target: IndirectDesignPath, targetExpr: expr.ValueExpr,
                    root: DesignPath, constrName: String): Unit = {
    addAssignExpr(target, targetExpr, root, constrName, true)
  }
  protected def addAssignExpr(target: IndirectDesignPath, targetExpr: expr.ValueExpr,
                    root: DesignPath, constrName: String, update: Boolean): Unit = {
    require(target.splitConnectedLink.isEmpty, "cannot set CONNECTED_LINK")
    val paramSourceRecord = (root, constrName, targetExpr)

    forcedParams.get(target) match {  // check for overassign based on forced status
      case Some(expr) if expr == (constrName, targetExpr) =>  // this is the forced param
        require(!params.valueDefinedAt(target), s"forced value must be set before value is resolved, prior ${paramSource(target)}")
        params.addNode(target, Seq(), update=true)  // allow updating and overwriting prior param record
      case Some(expr) => return  // ignore forced params - discard the new assign
      case None =>  // non-forced, check for and record over-assigns
        if (params.nodeDefinedAt(target)) {
          val record = discardOverassigns.getOrElseUpdate(target, OverassignRecord())
          record.assigns.add(paramSourceRecord)
          return // first set "wins"
        }
        params.addNode(target, Seq())  // first add is not update=True, actual processing happens in update()
    }

    val assign = AssignRecord(target, root, targetExpr)
    paramAssign.put(target, assign)
    paramSource.put(target, paramSourceRecord)

    if (update) {
      this.update()
    }
  }

  /** Sets a value directly (without the expr), convenience wrapper around addAssignment
    */
  def addAssignValue(target: IndirectDesignPath, value: ExprValue,
                     root: DesignPath, constrName: String): Unit = {
    addAssignExpr(target, ExprBuilder.ValueExpr.Literal(value.toLit), root, constrName)
  }

  /** Adds a directed assignment (param1 <- param2), checking for root reachability
    */
  def addAssignEqual(target: IndirectDesignPath, source: IndirectDesignPath,
                     root: DesignPath, constrName: String): Unit = {
    val pathPrefix = root.asIndirect.toLocalPath.steps
    val (sourcePrefix, sourcePostfix) = source.toLocalPath.steps.splitAt(pathPrefix.length)
    require(sourcePrefix == pathPrefix)
    addAssignExpr(target, ExprBuilder.ValueExpr.Ref(LocalPath(steps = sourcePostfix)),
      root, constrName=constrName)
  }

  /** Sets a value directly, and ignores subsequent assignments. Idempotent.
    * TODO: this still preserve semantics that forbid over-assignment, even if those don't do anything
    */
  def setForcedValue(target: DesignPath, value: ExprValue, constrName: String): Unit = {
    setForcedValue(target, value, constrName, true)
  }
  protected def setForcedValue(target: DesignPath, value: ExprValue, constrName: String, update: Boolean): Unit = {
    val targetIndirect = target.asIndirect
    val expr = ExprBuilder.ValueExpr.Literal(value.toLit)
    forcedParams.put(targetIndirect, (constrName, expr))
    addAssignExpr(targetIndirect, expr, DesignPath(), constrName, update)
  }

  /**
    * Returns the value of a parameter, or None if it does not have a value (yet?).
    * Can be used to check if parameters are resolved yet by testing against None.
    */
  def getValue(param: IndirectDesignPath): Option[ExprValue] = {
    resolveConnectedLink(param) match {
      case ConnectedLinkResult.ResolvedPath(path) => params.getValue(path)
      case ConnectedLinkResult.MissingConnectedLink(missing) => None
    }

  }
  def getValue(param: DesignPath): Option[ExprValue] = {
    // TODO should this be an implicit conversion?
    getValue(param.asIndirect)
  }

  def getConnectedLink(port: DesignPath): Option[DesignPath] = {
    connectedLink.getValue(ConnectedLinkRecord.ConnectedLink(port))
  }

  /**
    * Returns the type (as a class of ExprValue) of a parameter.
    */
  def getType(param: DesignPath): Option[Class[_ <: ExprValue]] = {
    paramTypes.get(param)
  }

  /**
    * Returns all parameters with a definition (eg, ValInit) but missing a concrete assignment.
    * Ignores indirect references.
    */
  def getUnsolved: Set[DesignPath] = {
    paramTypes.keySet.toSet -- params.knownValueKeys.flatMap(DesignPath.fromIndirectOption)
  }

  def getAllSolved: Map[IndirectDesignPath, ExprValue] = params.toMap

  def getErrors: Seq[CompilerError] = {
    val overassignErrors = discardOverassigns.map { case (target, record) =>
      val propagatedAssign = paramSource.get(target).map { case (root, constrName, value) =>
        CompilerError.OverAssignCause.Assign(target, root, constrName, value)
      }.toSeq
      val discardedAssigns = record.assigns.map { case (root, constrName, value) =>
        CompilerError.OverAssignCause.Assign(target, root, constrName, value)
      }
      CompilerError.OverAssign(target, propagatedAssign ++ discardedAssigns)
    }.toSeq

    // Also get all empty range assignments
    val emptyRangeErrors = params.toMap.collect {
      case (targetPath, RangeEmpty) =>
        paramSource.get(targetPath).map { case (root, constrName, value) =>
          CompilerError.EmptyRange(targetPath, root, constrName, value)
        }
    }.flatten.toSeq

    overassignErrors ++ emptyRangeErrors
  }
}
