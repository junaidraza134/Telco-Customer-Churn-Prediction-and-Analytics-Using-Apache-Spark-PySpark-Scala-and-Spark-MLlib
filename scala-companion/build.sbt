name := "telco-churn-scala"
version := "0.1.0"
scalaVersion := "2.12.18"

val sparkVersion = "3.5.3"
val isProvided = sys.env.getOrElse("SPARK_PROVIDED", "false").toBoolean
val sparkScope = if (isProvided) "provided" else "compile"

libraryDependencies ++= Seq(
  "org.scala-lang"   % "scala-reflect" % scalaVersion.value,
  "org.apache.spark" %% "spark-core"   % sparkVersion % sparkScope,
  "org.apache.spark" %% "spark-sql"    % sparkVersion % sparkScope
)

fork := true

javaOptions ++= Seq(
  "--add-opens=java.base/java.lang=ALL-UNNAMED",
  "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED",
  "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
  "--add-opens=java.base/java.io=ALL-UNNAMED",
  "--add-opens=java.base/java.net=ALL-UNNAMED",
  "--add-opens=java.base/java.nio=ALL-UNNAMED",
  "--add-opens=java.base/java.util=ALL-UNNAMED",
  "--add-opens=java.base/java.util.concurrent=ALL-UNNAMED",
  "--add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED",
  "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED",
  "--add-opens=java.base/sun.nio.cs=ALL-UNNAMED",
  "--add-opens=java.base/sun.security.action=ALL-UNNAMED",
  "--add-opens=java.base/sun.util.calendar=ALL-UNNAMED",
  "--add-opens=java.security.jgss/sun.security.krb5=ALL-UNNAMED"
)
