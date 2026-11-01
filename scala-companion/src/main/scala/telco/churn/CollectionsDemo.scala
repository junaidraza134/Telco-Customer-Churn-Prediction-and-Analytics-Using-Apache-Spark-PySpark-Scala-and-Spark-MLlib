package telco.churn

import scala.collection.mutable.ArrayBuffer

object CollectionsDemo {

  def assessRiskTier(contract: String, internet: String): String = {
    // Pattern matching on (Contract, InternetService)
    (contract, internet) match {
      case ("Month-to-month", "Fiber optic") => "Critical"
      case ("Month-to-month", _)             => "Elevated"
      case ("One year", _)                   => "Watch"
      case ("Two year", _)                   => "Stable"
      case _                                 => "Standard"
    }
  }

  def run(customers: List[Customer]): Unit = {
    println("\n" + "=" * 60)
    println("SCALA FUNCTIONAL COLLECTIONS DEMO")
    println("=" * 60)
    println(s"Received immutable customer list: size = ${customers.size}")

    // 1. Partition: split into churned and retained
    val (churned, retained) = customers.partition(_.Churn == "Yes")
    println(s"Partitioned: Churned = ${churned.size}, Retained = ${retained.size}")

    // 2. Map, Filter, Sum
    val tenureThreshold = 24
    val longTenureChurnedRevenue = churned
      .filter(_.tenure > tenureThreshold)
      .map(_.MonthlyCharges)
      .sum
    println(f"Long-tenure churned revenue (> $tenureThreshold mo): $$${longTenureChurnedRevenue}%.2f")

    // 3. Closures: external threshold captured
    val highMonthlyThreshold = 80.0
    val isHighValue: Customer => Boolean = c => c.MonthlyCharges >= highMonthlyThreshold
    val highValueChurnCount = churned.count(isHighValue)
    println(s"High-value churners (>= $$${highMonthlyThreshold}): $highValueChurnCount")

    // 4. groupBy -> Map
    val customersByContract: Map[String, List[Customer]] = customers.groupBy(_.Contract)
    println("\nContract Breakdown via groupBy:")
    customersByContract.foreach { case (contract, list) =>
      val churnCount = list.count(_.Churn == "Yes")
      val churnRate = (churnCount.toDouble / list.size) * 100
      val avgMonthly = list.map(_.MonthlyCharges).sum / list.size
      println(f" - $contract%-16s: Count=${list.size}%5d, ChurnRate=$churnRate%6.2f%%, AvgMonthly=$$$avgMonthly%5.2f")
    }

    // 5. foldLeft: total charges calculation
    val totalRevenueCollected = customers.foldLeft(0.0)((acc, c) => acc + c.TotalCharges)
    println(f"\nTotal lifetime revenue via foldLeft: $$${totalRevenueCollected}%,.2f")

    // 6. Pattern matching risk tier assessment
    val sampleAssessments = customers.take(5).map { c =>
      val tier = assessRiskTier(c.Contract, c.InternetService)
      (c.customerID, c.Contract, c.InternetService, tier)
    }
    println("\nPattern Matching Risk Tier Samples:")
    sampleAssessments.foreach { case (id, contract, internet, tier) =>
      println(f" - ID: $id%-12s | Contract: $contract%-16s | Internet: $internet%-12s | Tier: $tier")
    }

    // 7. Immutable Set/Map vs Mutable ArrayBuffer
    val uniqueContracts: Set[String] = customers.map(_.Contract).toSet
    println(s"\nImmutable Set of Contracts: $uniqueContracts")

    val buffer = new ArrayBuffer[Double]()
    for (c <- customers.take(10)) {
      buffer += c.MonthlyCharges
    }
    println(s"Mutable ArrayBuffer sample buffer size: ${buffer.size}, sum = ${buffer.sum}")

    // 8. Composable rule list: List[Customer => Double]
    val rule1: Customer => Double = c => if (c.Contract == "Month-to-month") 0.20 else 0.05
    val rule2: Customer => Double = c => if (c.InternetService == "Fiber optic") 0.15 else 0.0
    val rule3: Customer => Double = c => if (c.TotalServices < 2) 0.10 else -0.05

    val rules: List[Customer => Double] = List(rule1, rule2, rule3)
    val compositeRiskScore: Customer => Double = c => rules.map(rule => rule(c)).sum

    println("\nComposable Rule List Risk Scores (First 3 Customers):")
    customers.take(3).foreach { c =>
      val score = compositeRiskScore(c)
      println(f" - ${c.customerID}: Base risk multiplier = $score%.2f")
    }
  }
}
