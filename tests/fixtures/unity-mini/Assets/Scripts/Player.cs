using UnityEngine;

public class Player : MonoBehaviour
{
    public AudioSource audioSource;
    public AudioClip hurtClip;
    int hp = 3;

    void Update()
    {
        if (Input.GetButtonDown("Jump")) Jump();
    }

    void Jump()
    {
        GetComponent<Rigidbody2D>().velocity = Vector2.up * 8f;
    }

    void OnTriggerEnter2D(Collider2D other)
    {
        if (other.CompareTag("Coin")) CollectCoin(other.gameObject);
    }

    void CollectCoin(GameObject coin)
    {
        Destroy(coin);
    }

    public void TakeDamage(int amount)
    {
        audioSource.PlayOneShot(hurtClip);
        hp -= amount;
        if (hp <= 0) Die();
    }

    void Die() { GameManager.Instance.GameOver(); }
}
