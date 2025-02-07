package edg.compiler

import org.scalatest._
import org.scalatest.flatspec.AnyFlatSpec
import matchers.should.Matchers._
import edg.ElemBuilder._
import edg.ExprBuilder.{Ref, ValInit, ValueExpr}
import edg.{CompilerTestUtil, wir}
import edg.wir.{EdgirLibrary, IndirectDesignPath, IndirectStep, Refinements}
import org.scalatest.exceptions.TestFailedException

import scala.collection.SeqMap


/** Tests compiler parameter and expression evaluation using ASSIGN constraints.
  */
class CompilerEvaluationTest extends AnyFlatSpec with CompilerTestUtil {
  import edgir.expr.expr.UnarySetExpr.Op
  val library = Library(
    ports = Seq(
      Port.Port("sourcePort",
        params = SeqMap(
          "floatVal" -> ValInit.Floating,
        )
      ),
      Port.Port("sinkPort",
        params = SeqMap(
          "sumVal" -> ValInit.Floating,
          "intersectVal" -> ValInit.Range,
        )
      ),
    ),
    blocks = Seq(
      Block.Block("sourceBlock",
        params = SeqMap(
          "floatVal" -> ValInit.Floating,
        ),
        ports = SeqMap(
          "port" -> Port.Library("sourcePort"),
        ),
        constraints = SeqMap(
          "propFloatVal" -> ValueExpr.Assign(Ref("port", "floatVal"), ValueExpr.Ref("floatVal")),
        )
      ),
      Block.Block("sinkBlock",
        params = SeqMap(
          "sumVal" -> ValInit.Floating,
          "intersectVal" -> ValInit.Range,
        ),
        ports = SeqMap(
          "port" -> Port.Library("sinkPort"),
        ),
        constraints = SeqMap(
          "propSumVal" -> ValueExpr.Assign(Ref("port", "sumVal"), ValueExpr.Ref("sumVal")),
          "propIntersectVal" -> ValueExpr.Assign(Ref("port", "intersectVal"), ValueExpr.Ref("intersectVal")),
        )
      ),
      Block.Block("sourceContainerBlock",
        params = SeqMap(
          "floatVal" -> ValInit.Floating,
        ),
        ports = SeqMap(
          "port" -> Port.Library("sourcePort"),
        ),
        blocks = SeqMap(
          "inner" -> Block.Library("sourceBlock")
        ),
        constraints = SeqMap(
          "export" -> Constraint.Exported(Ref("port"), Ref("inner", "port")),
          "floatAssign" -> Constraint.Assign(Ref("inner", "floatVal"), ValueExpr.Ref("floatVal")),
        )
      ),
    ),
    links = Seq(
      Link.Link("link",
        ports = SeqMap(
          "source" -> Port.Library("sourcePort"),
          "sinks" -> Port.Array("sinkPort"),
        ),
        params = SeqMap(
          "sourceFloat" -> ValInit.Floating,
          "sinkSum" -> ValInit.Floating,
          "sinkIntersect" -> ValInit.Range,
        ),
        constraints = SeqMap(
          "calcSourceFloat" -> ValueExpr.Assign(Ref("sourceFloat"), ValueExpr.Ref("source", "floatVal")),
          "calcSinkSum" -> ValueExpr.Assign(Ref("sinkSum"), ValueExpr.UnarySetOp(Op.SUM,
            ValueExpr.MapExtract(Ref("sinks"), Ref("sumVal"))
          )),
          "calcSinkIntersect" -> ValueExpr.Assign(Ref("sinkIntersect"), ValueExpr.UnarySetOp(Op.INTERSECTION,
            ValueExpr.MapExtract(Ref("sinks"), Ref("intersectVal"))
          )),
        )
      ),
    )
  )

  "Compiler on design with assign constraints" should "propagate and evaluate values" in {
    val inputDesign = Design(Block.Block("designTop",
      blocks = SeqMap(
        "source" -> Block.Library("sourceBlock"),
        "sink0" -> Block.Library("sinkBlock"),
      ),
      links = SeqMap(
        "link" -> Link.Library("link")
      ),
      constraints = SeqMap(
        "sourceConnect" -> Constraint.Connected(Ref("source", "port"), Ref("link", "source")),
        "sink0Connect" -> Constraint.Connected(Ref("sink0", "port"), Ref.Allocate(Ref("link", "sinks"))),
        "sourceFloatVal" -> Constraint.Assign(Ref("source", "floatVal"), ValueExpr.Literal(3.0)),
        "sink0SumVal" -> Constraint.Assign(Ref("sink0", "sumVal"), ValueExpr.Literal(1.0)),
        "sink0IntersectVal" -> Constraint.Assign(Ref("sink0", "intersectVal"), ValueExpr.Literal(5.0, 7.0)),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    // Check one-step prop
    compiler.getValue(IndirectDesignPath() + "source" + "floatVal") should equal(Some(FloatValue(3.0)))
    compiler.getValue(IndirectDesignPath() + "sink0" + "sumVal") should equal(Some(FloatValue(1.0)))
    compiler.getValue(IndirectDesignPath() + "sink0" + "intersectVal") should equal(Some(RangeValue(5.0, 7.0)))

    // Check block port prop
    compiler.getValue(IndirectDesignPath() + "source" + "port" + "floatVal") should equal(Some(FloatValue(3.0)))
    compiler.getValue(IndirectDesignPath() + "sink0" + "port" + "sumVal") should equal(Some(FloatValue(1.0)))
    compiler.getValue(IndirectDesignPath() + "sink0" + "port" + "intersectVal") should equal(Some(RangeValue(5.0, 7.0)))

    // Check link port prop
    compiler.getValue(IndirectDesignPath() + "link" + "source" + "floatVal") should equal(Some(FloatValue(3.0)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + "0" + "sumVal") should equal(Some(FloatValue(1.0)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + "0" + "intersectVal") should equal(Some(RangeValue(5.0, 7.0)))

    // check link reductions
    compiler.getValue(IndirectDesignPath() + "link" + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinkSum") should equal(Some(FloatValue(1.0)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinkIntersect") should equal(Some(RangeValue(5.0, 7.0)))

    // check CONNECTED_LINK
    val linkThroughSource = IndirectDesignPath() + "source" + "port" + IndirectStep.ConnectedLink
    compiler.getValue(linkThroughSource + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(linkThroughSource + "sinkSum") should equal(Some(FloatValue(1.0)))
    compiler.getValue(linkThroughSource + "sinkIntersect") should equal(Some(RangeValue(5.0, 7.0)))
    compiler.getValue(linkThroughSource + IndirectStep.Name) should equal(Some(TextValue("link")))

    val linkThroughSink0 = IndirectDesignPath() + "sink0" + "port" + IndirectStep.ConnectedLink
    compiler.getValue(linkThroughSink0 + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(linkThroughSink0 + "sinkSum") should equal(Some(FloatValue(1.0)))
    compiler.getValue(linkThroughSink0 + "sinkIntersect") should equal(Some(RangeValue(5.0, 7.0)))
    compiler.getValue(linkThroughSink0 + IndirectStep.Name) should equal(Some(TextValue("link")))

    // check IS_CONNECTED
    compiler.getValue(IndirectDesignPath() + "source" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "sink0" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "source" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + "0" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + IndirectStep.Length) should equal(
      Some(IntValue(1)))
  }

  "Compiler on design with assign constraints and multiple connects to link" should "propagate and evaluate values" in {
    val inputDesign = Design(Block.Block("topDesign",
      blocks = SeqMap(
        "source" -> Block.Library("sourceBlock"),
        "sink0" -> Block.Library("sinkBlock"),
        "sink1" -> Block.Library("sinkBlock"),
        "sink2" -> Block.Library("sinkBlock"),
      ),
      links = SeqMap(
        "link" -> Link.Library("link")
      ),
      constraints = SeqMap(
        "sourceConnect" -> Constraint.Connected(Ref("source", "port"), Ref("link", "source")),
        "sink0Connect" -> Constraint.Connected(Ref("sink0", "port"), Ref.Allocate(Ref("link", "sinks"))),
        "sink1Connect" -> Constraint.Connected(Ref("sink1", "port"), Ref.Allocate(Ref("link", "sinks"))),
        "sink2Connect" -> Constraint.Connected(Ref("sink2", "port"), Ref.Allocate(Ref("link", "sinks"))),

        "sourceFloatVal" -> Constraint.Assign(Ref("source", "floatVal"), ValueExpr.Literal(3.0)),

        "sink0SumVal" -> Constraint.Assign(Ref("sink0", "sumVal"), ValueExpr.Literal(1.0)),
        "sink0IntersectVal" -> Constraint.Assign(Ref("sink0", "intersectVal"), ValueExpr.Literal(4.0, 7.0)),
        "sink1SumVal" -> Constraint.Assign(Ref("sink1", "sumVal"), ValueExpr.Literal(2.0)),
        "sink1IntersectVal" -> Constraint.Assign(Ref("sink1", "intersectVal"), ValueExpr.Literal(5.0, 8.0)),
        "sink2SumVal" -> Constraint.Assign(Ref("sink2", "sumVal"), ValueExpr.Literal(3.0)),
        "sink2IntersectVal" -> Constraint.Assign(Ref("sink2", "intersectVal"), ValueExpr.Literal(6.0, 9.0)),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    // check link reductions
    compiler.getValue(IndirectDesignPath() + "link" + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinkSum") should equal(Some(FloatValue(6.0)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinkIntersect") should equal(Some(RangeValue(6.0, 7.0)))

    // check CONNECTED_LINK
    val linkThroughSink0 = IndirectDesignPath() + "sink0" + "port" + IndirectStep.ConnectedLink
    compiler.getValue(linkThroughSink0 + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(linkThroughSink0 + "sinkSum") should equal(Some(FloatValue(6.0)))
    compiler.getValue(linkThroughSink0 + "sinkIntersect") should equal(Some(RangeValue(6.0, 7.0)))
    compiler.getValue(linkThroughSink0 + IndirectStep.Name) should equal(Some(TextValue("link")))

    val linkThroughSink1 = IndirectDesignPath() + "sink1" + "port" + IndirectStep.ConnectedLink
    compiler.getValue(linkThroughSink1 + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(linkThroughSink1 + "sinkSum") should equal(Some(FloatValue(6.0)))
    compiler.getValue(linkThroughSink1 + "sinkIntersect") should equal(Some(RangeValue(6.0, 7.0)))
    compiler.getValue(linkThroughSink1 + IndirectStep.Name) should equal(Some(TextValue("link")))

    val linkThroughSink2 = IndirectDesignPath() + "sink2" + "port" + IndirectStep.ConnectedLink
    compiler.getValue(linkThroughSink2 + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(linkThroughSink2 + "sinkSum") should equal(Some(FloatValue(6.0)))
    compiler.getValue(linkThroughSink2 + "sinkIntersect") should equal(Some(RangeValue(6.0, 7.0)))
    compiler.getValue(linkThroughSink2 + IndirectStep.Name) should equal(Some(TextValue("link")))

    // check IS_CONNECTED
    compiler.getValue(IndirectDesignPath() + "source" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "sink0" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "sink1" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "sink2" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "source" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + "0" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + "1" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + "2" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + IndirectStep.Length) should equal(
      Some(IntValue(3)))
  }

  "Compiler on design with empty port arrays" should "propagate and evaluate values" in {
    val inputDesign = Design(Block.Block("topDesign",
      blocks = SeqMap(
        "source" -> Block.Library("sourceBlock"),
      ),
      links = SeqMap(
        "link" -> Link.Library("link")
      ),
      constraints = SeqMap(
        "sourceConnect" -> Constraint.Connected(Ref("source", "port"), Ref("link", "source")),
        "sourceFloatVal" -> Constraint.Assign(Ref("source", "floatVal"), ValueExpr.Literal(3.0)),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    // check link reductions
    compiler.getValue(IndirectDesignPath() + "link" + "sinkSum") should equal(Some(FloatValue(0.0)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinkIntersect") should equal(
      Some(RangeValue(Float.NegativeInfinity, Float.PositiveInfinity)))
    compiler.getValue(IndirectDesignPath() + "link" + "sinks" + IndirectStep.Length) should equal(
      Some(IntValue(0)))
  }

  "Compiler on design with exports" should "propagate and evaluate values" in {
    val inputDesign = Design(Block.Block("topDesign",
      blocks = SeqMap(
        "source" -> Block.Library("sourceContainerBlock"),
        "sink0" -> Block.Library("sinkBlock"),
      ),
      links = SeqMap(
        "link" -> Link.Library("link")
      ),
      constraints = SeqMap(
        "sourceConnect" -> Constraint.Connected(Ref("source", "port"), Ref("link", "source")),
        "sink0Connect" -> Constraint.Connected(Ref("sink0", "port"), Ref.Allocate(Ref("link", "sinks"))),
        "sourceFloatVal" -> Constraint.Assign(Ref("source", "floatVal"), ValueExpr.Literal(3.0)),
        "sink0SumVal" -> Constraint.Assign(Ref("sink0", "sumVal"), ValueExpr.Literal(1.0)),
        "sink0IntersectVal" -> Constraint.Assign(Ref("sink0", "intersectVal"), ValueExpr.Literal(5.0, 7.0)),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    // check CONNECTED_LINK through outer (direct connection)
    val linkThroughSource = IndirectDesignPath() + "source" + "port" + IndirectStep.ConnectedLink
    compiler.getValue(linkThroughSource + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(linkThroughSource + "sinkSum") should equal(Some(FloatValue(1.0)))
    compiler.getValue(linkThroughSource + "sinkIntersect") should equal(Some(RangeValue(5.0, 7.0)))
    compiler.getValue(linkThroughSource + IndirectStep.Name) should equal(Some(TextValue("link")))

    // check CONNECTED_LINK through inner (via exports)
    val linkThroughInnerSource = IndirectDesignPath() + "source" + "inner" + "port" + IndirectStep.ConnectedLink
    compiler.getValue(linkThroughInnerSource + "sourceFloat") should equal(Some(FloatValue(3.0)))
    compiler.getValue(linkThroughInnerSource + "sinkSum") should equal(Some(FloatValue(1.0)))
    compiler.getValue(linkThroughInnerSource + "sinkIntersect") should equal(Some(RangeValue(5.0, 7.0)))
    compiler.getValue(linkThroughInnerSource + IndirectStep.Name) should equal(Some(TextValue("link")))

    // check IS_CONNECTED
    compiler.getValue(IndirectDesignPath() + "source" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
    compiler.getValue(IndirectDesignPath() + "source" + "inner" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(true)))
  }

  "Compiler on design with disconnected ports" should "indicate disconnected" in {
    val inputDesign = Design(Block.Block("topDesign",
      blocks = SeqMap(
        "source" -> Block.Library("sourceBlock"),
      ),
      constraints = SeqMap(
        // to not give an unsolved parameter error
        "sourceFloatVal" -> Constraint.Assign(Ref("source", "floatVal"), ValueExpr.Literal(3.0)),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    // check IS_CONNECTED
    compiler.getValue(IndirectDesignPath() + "source" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(false)))
  }

  "Compiler on design with disconnected link ports" should "indicate disconnected" in {
    val inputDesign = Design(Block.Block("topDesign",
      links = SeqMap(
        "link" -> Link.Library("link")
      ),
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    // check link reductions
    compiler.getValue(IndirectDesignPath() + "link" + "source" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(false)))
  }

  "Compiler on design with disconnected exported ports" should "indicate disconnected" in {
    val inputDesign = Design(Block.Block("topDesign",
      blocks = SeqMap(
        "source" -> Block.Library("sourceContainerBlock"),
      ),
      constraints = SeqMap(
        // to not give an unsolved parameter error
        "sourceFloatVal" -> Constraint.Assign(Ref("source", "floatVal"), ValueExpr.Literal(3.0)),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    // check IS_CONNECTED
    compiler.getValue(IndirectDesignPath() + "source" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(false)))
    compiler.getValue(IndirectDesignPath() + "source" + "inner" + "port" + IndirectStep.IsConnected) should equal(
      Some(BooleanValue(false)))
  }

  "Compiler on design with assign constraints" should "resolve if-then-else without defined non-taken branch" in {
    val inputDesign = Design(Block.Block("topDesign",
      params = SeqMap(
        "condTrue" -> ValInit.Boolean,
        "condFalse" -> ValInit.Boolean,
        "defined" -> ValInit.Integer,
        "undefined" -> ValInit.Integer,
        "ifTrue" -> ValInit.Integer,
        "ifFalse" -> ValInit.Integer,
        "ifUndef" -> ValInit.Integer,
      ),
      constraints = SeqMap(
        "condTrue" -> Constraint.Assign(Ref("condTrue"), ValueExpr.Literal(true)),
        "condFalse" -> Constraint.Assign(Ref("condFalse"), ValueExpr.Literal(false)),
        "defined" -> Constraint.Assign(Ref("defined"), ValueExpr.Literal(45)),
        "ifTrue" -> Constraint.Assign(Ref("ifTrue"),
          ValueExpr.IfThenElse(ValueExpr.Ref("condTrue"), ValueExpr.Ref("defined"), ValueExpr.Ref("undefined"))
        ),
        "ifFalse" -> Constraint.Assign(Ref("ifFalse"),
          ValueExpr.IfThenElse(ValueExpr.Ref("condFalse"), ValueExpr.Ref("undefined"), ValueExpr.Ref("defined"))
        ),
        "ifUndef" -> Constraint.Assign(Ref("ifUndef"),
          ValueExpr.IfThenElse(ValueExpr.Ref("condFalse"), ValueExpr.Ref("defined"), ValueExpr.Ref("undefined"))
        ),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)

    compiler.getValue(IndirectDesignPath() + "ifUndef") should equal(None)
    compiler.getValue(IndirectDesignPath() + "ifTrue") should equal(Some(IntValue(45)))
    compiler.getValue(IndirectDesignPath() + "ifFalse") should equal(Some(IntValue(45)))
  }

  "Compiler on design with true assertions" should "not fail" in {
    val inputDesign = Design(Block.Block("topDesign",
      constraints = SeqMap(
        "requireTrue" -> ValueExpr.Literal(true),
      )
    ))
    val (compiler, compiled) = testCompile(inputDesign, library)
  }

  "Compiler on design with false assertions" should "fail" in {
    val inputDesign = Design(Block.Block("topDesign",
      constraints = SeqMap(
        "requireFalse" -> ValueExpr.Literal(false),
      )
    ))
    val compiler = new Compiler(inputDesign, new EdgirLibrary(library), Refinements())
    val compiled = compiler.compile()
    val assertionErrors = new DesignAssertionCheck(compiler).map(compiled)
    assertionErrors.size shouldBe 1
    assertionErrors.head.getClass shouldBe classOf[CompilerError.FailedAssertion]

    an [TestFailedException] should be thrownBy testCompile(inputDesign, library)  // test the test helper code
  }

  "Compiler on design with missing assertions" should "fail" in {
    val inputDesign = Design(Block.Block("topDesign",
      params = SeqMap(
        "missing" -> ValInit.Boolean,
      ),
      constraints = SeqMap(
        "requireMissing" -> ValueExpr.Ref("missing"),
      )
    ))
    val compiler = new Compiler(inputDesign, new EdgirLibrary(library), Refinements())
    val compiled = compiler.compile()
    val assertionErrors = new DesignAssertionCheck(compiler).map(compiled)
    assertionErrors.size shouldBe 1
    assertionErrors.head.getClass shouldBe classOf[CompilerError.MissingAssertion]

    an [TestFailedException] should be thrownBy testCompile(inputDesign, library)  // test the test helper code
  }
}
