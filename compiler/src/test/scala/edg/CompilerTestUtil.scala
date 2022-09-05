package edg

import edg.compiler.{Compiler, PartialCompile}
import edg.wir.{EdgirLibrary, Refinements}
import edgir.schema.schema.{Design, Library}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers._


trait CompilerTestUtil extends AnyFlatSpec {
  def testCompile(inputDesign: Design, library: Library, refinements: Refinements=Refinements(),
                  expectedDesign: Option[Design] = None): (Compiler, Design) = {
    val compiler = new Compiler(inputDesign, new EdgirLibrary(library), refinements)
    val compiled = compiler.compile()
    compiler.getErrors() shouldBe empty
    expectedDesign match {
      case Some(expectedDesign) => compiled should equal(expectedDesign)
      case _ =>
    }
    (compiler, compiled)
  }
}
