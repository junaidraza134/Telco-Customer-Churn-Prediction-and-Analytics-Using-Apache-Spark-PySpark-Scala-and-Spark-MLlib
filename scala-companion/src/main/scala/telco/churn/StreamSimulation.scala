package telco.churn

import scala.util.Random

object StreamSimulation {

  case class NetworkEvent(
    eventId: Long,
    customerID: String,
    latencyMs: Double,
    packetLossPct: Double,
    isIncident: Boolean
  )

  def run(): Unit = {
    println("\n" + "=" * 60)
    println("SCALA 2.12 LAZY STREAM SIMULATION")
    println("=" * 60)

    val rng = new Random(42)
    var materializationCount = 0

    // Infinite Stream.from(1).map(...) with seeded Random(42)
    val stream: Stream[NetworkEvent] = Stream.from(1).map { id =>
      materializationCount += 1
      val latency = 15.0 + rng.nextDouble() * 120.0
      val packetLoss = rng.nextDouble() * 5.0
      val incident = latency > 80.0 || packetLoss > 3.0
      NetworkEvent(
        eventId = id.toLong,
        customerID = f"CUST-${rng.nextInt(7043)}%04d",
        latencyMs = latency,
        packetLossPct = packetLoss,
        isIncident = incident
      )
    }

    println("Stream defined: Stream.from(1).map(...)")
    println(s"Materialized events before consumption: $materializationCount")

    // Materialize first 10 incident events only
    val sampleIncidents = stream
      .filter(_.isIncident)
      .take(10)
      .toList

    println(s"Materialized exactly ${sampleIncidents.size} incident events:")
    sampleIncidents.foreach { ev =>
      println(f" [Event ${ev.eventId}%4d] ${ev.customerID} | Latency: ${ev.latencyMs}%5.1f ms | Loss: ${ev.packetLossPct}%4.1f%%")
    }
    println(s"Total events generated in stream to find 10 incidents: $materializationCount")
    println("Lazy evaluation confirmed: Infinite stream did not exhaust memory.")
  }
}
